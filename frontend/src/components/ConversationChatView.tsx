import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  fetchConversationMessages,
  streamConversationMessage,
} from "../api/client";
import { useApp } from "../context/AppContext";
import {
  applyStreamStatus,
  appendSynthesizerOutput,
  completeAgentOutput,
  type AgentOutput,
} from "../lib/pipelineAgents";
import type { ConversationScope, PersistedMessage, SearchSource } from "../types/api";
import { ChatInput } from "./ChatInput";
import { renderMarkdown, SourcePreviewModal } from "./SourceCard";
import { ThinkingPanel } from "./ThinkingPanel";

function citationToSource(citation: Record<string, unknown>, index: number): SearchSource {
  const title = String(citation.title ?? `Source ${index + 1}`);
  const url = typeof citation.url === "string" ? citation.url : "";
  const sourcePath = typeof citation.source_path === "string" ? citation.source_path : url;
  const content = String(citation.content ?? citation.snippet ?? "");

  return {
    segment_id: String(citation.segment_id ?? url ?? `source-${index}`),
    file_id: String(citation.file_id ?? url ?? `source-${index}`),
    modality: citation.modality === "audio" || citation.modality === "video" ? citation.modality : "text",
    title,
    content,
    source_path: sourcePath,
    start_time: typeof citation.start_time === "number" ? citation.start_time : null,
    end_time: typeof citation.end_time === "number" ? citation.end_time : null,
    score: typeof citation.score === "number" ? citation.score : 1,
  };
}

function sourcesFromMessage(message: PersistedMessage): SearchSource[] {
  return message.citations.map((citation, index) => citationToSource(citation, index));
}

function MessageBubble({
  message,
  streaming = false,
  onSourceClick,
}: {
  message: PersistedMessage;
  streaming?: boolean;
  onSourceClick: (source: SearchSource, index: number) => void;
}) {
  const isUser = message.role === "user";
  const sources = sourcesFromMessage(message);

  return (
    <article
      className={
        isUser
          ? "ml-auto max-w-[76%] rounded-lg rounded-tr-sm border border-[var(--app-border)] bg-[var(--app-chat-user)] px-3 py-2 text-sm leading-6 text-[var(--app-text)] shadow-sm backdrop-blur-xl"
          : "mr-auto max-w-[76%] rounded-lg rounded-tl-sm border border-[var(--app-border)] bg-[var(--app-chat-assistant)] px-3 py-2 text-sm leading-6 text-[var(--app-text)] shadow-sm backdrop-blur-xl"
      }
    >
      {isUser ? (
        <p className="whitespace-pre-wrap">{message.content}</p>
      ) : (
        <div className="space-y-1">
          {renderMarkdown(message.content, sources, onSourceClick)}
          {streaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-900 align-middle" />
          )}
        </div>
      )}
      {message.status === "failed" && <span className="mt-2 block text-xs text-rose-500">Failed</span>}
    </article>
  );
}

export function ConversationChatView({ scope }: { scope: ConversationScope }) {
  const { state, selectConversation } = useApp();
  const projectId = scope === "project" ? state.project?.projectId : undefined;
  const [conversationId, setConversationId] = useState<string | null>(state.activeConversationId);
  const [messages, setMessages] = useState<PersistedMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [agentOutputs, setAgentOutputs] = useState<AgentOutput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<{ source: SearchSource; index: number } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setConversationId(state.activeConversationId);
  }, [state.activeConversationId]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setAgentOutputs([]);
      return;
    }
    fetchConversationMessages(conversationId)
      .then((result) => setMessages(result.messages))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Failed to load messages"));
  }, [conversationId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  function notifyConversationListChanged() {
    window.dispatchEvent(
      new CustomEvent("scrutinize:conversations-changed", {
        detail: { scope, projectId },
      }),
    );
  }

  async function submit() {
    const content = draft.trim();
    if (!content || loading) return;
    setLoading(true);
    setError(null);
    setDraft("");
    setStreamingText("");
    setAgentOutputs([]);

    const clientMessageId = crypto.randomUUID();
    const optimistic: PersistedMessage = {
      id: clientMessageId,
      conversation_id: conversationId ?? "pending",
      role: "user",
      content,
      status: "completed",
      citations: [],
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimistic]);

    try {
      let id = conversationId;
      if (!id) {
        const created = await createConversation(scope, projectId);
        id = created.id;
        setConversationId(id);
        selectConversation(id, scope === "general" ? "general-chat" : "project");
        notifyConversationListChanged();
      }

      await streamConversationMessage(id, content, clientMessageId, (event) => {
        if (event.event === "message.accepted" && event.data.user_message) {
          setMessages((current) =>
            current.map((message) => (message.id === clientMessageId ? event.data.user_message! : message)),
          );
        }
        if (event.event === "status") {
          const step = event.data.step ?? event.data.phase;
          if (!step) return;
          setAgentOutputs((current) =>
            applyStreamStatus(current, {
              ...event.data,
              step,
              message: event.data.message ?? event.data.label,
            }),
          );
        }
        if (event.event === "delta") {
          setStreamingText((current) => current + event.data.text);
          setAgentOutputs((current) => appendSynthesizerOutput(current, event.data.text));
        }
        if (event.event === "message.completed") {
          setAgentOutputs((current) =>
            completeAgentOutput(current, "synthesis", null, event.data.assistant_message.content),
          );
          setMessages((current) => [...current.filter((message) => message.id !== event.data.assistant_message.id), event.data.assistant_message]);
          setStreamingText("");
          notifyConversationListChanged();
        }
        if (event.event === "error") setError(event.data.message);
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Message failed");
    } finally {
      setLoading(false);
      setAgentOutputs((current) =>
        current.map((entry) => (entry.status === "active" ? { ...entry, status: "complete" } : entry)),
      );
    }
  }

  const active = messages.length > 0 || Boolean(conversationId);
  const composerDocked = active || loading;
  const contextLabel = scope === "general" ? "Web chat" : state.project?.projectName ?? "Project chat";
  const inputProps = {
    value: draft,
    onChange: setDraft,
    onSubmit: () => void submit(),
    loading,
    disabled: !state.apiConnected,
    webOnly: scope === "general",
  };

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-[var(--app-chat-bg)]">
      <div
        className={`absolute inset-0 z-10 flex flex-col items-center justify-center px-4 pb-16 transition-all duration-500 ease-out ${
          composerDocked
            ? "pointer-events-none -translate-y-6 opacity-0"
            : "translate-y-0 opacity-100"
        }`}
        aria-hidden={composerDocked}
      >
        <div className="mb-8 text-center">
          <span className="inline-flex rounded-full bg-black/5 px-3 py-1 text-xs font-medium text-zinc-600">
            {contextLabel}
          </span>
          <p className="mt-3 text-sm text-zinc-500">Start a new conversation from the box below.</p>
        </div>
        <div className="w-full max-w-3xl">
          <ChatInput {...inputProps} />
        </div>
      </div>

      <div
        className={`min-h-0 flex-1 overflow-y-auto px-4 py-5 transition-opacity duration-500 ease-out ${
          composerDocked ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="mx-auto flex w-full max-w-3xl flex-col items-stretch gap-3">
          {messages.filter((message) => message.role !== "system").map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onSourceClick={(source, index) => setActiveSource({ source, index })}
            />
          ))}
          <ThinkingPanel outputs={agentOutputs} loading={loading} />
          {streamingText && (
            <MessageBubble
              message={{
                id: "streaming",
                conversation_id: conversationId ?? "streaming",
                role: "assistant",
                content: streamingText,
                status: "streaming",
                citations: [],
                created_at: new Date().toISOString(),
                completed_at: null,
              }}
              streaming
              onSourceClick={(source, index) => setActiveSource({ source, index })}
            />
          )}
          {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div ref={endRef} />
        </div>
      </div>
      <div
        className={`shrink-0 overflow-visible px-4 pb-6 pt-2 transition-all duration-500 ease-out ${
          composerDocked ? "chat-dock-enter max-h-[18rem]" : "max-h-0 overflow-hidden pb-0 pt-0 opacity-0"
        }`}
      >
        <div className="mx-auto w-full max-w-3xl">
          <ChatInput {...inputProps} />
        </div>
      </div>
      {activeSource && (
        <SourcePreviewModal
          source={activeSource.source}
          index={activeSource.index}
          onClose={() => setActiveSource(null)}
        />
      )}
    </div>
  );
}
