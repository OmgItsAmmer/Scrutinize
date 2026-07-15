import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  fetchConversationMessages,
  fetchConversationSources,
  streamConversationMessage,
  uploadConversationSource,
  type ConversationSource,
} from "../api/client";
import { useApp } from "../context/AppContext";
import {
  applyStreamStatus,
  appendSynthesizerOutput,
  completeAgentOutput,
  type AgentOutput,
} from "../lib/pipelineAgents";
import {
  CHAT_TOOLS,
  parseMessageWithPdf,
  type ChatToolId,
} from "../lib/chatTools";
import type { ConversationScope, PersistedMessage, SearchSource } from "../types/api";
import { ChatInput } from "./ChatInput";
import { PdfDownloadButton } from "./PdfDownloadButton";
import { renderMarkdown, SourcePreviewModal, CitationButton } from "./SourceCard";
import { ThinkingPanel } from "./ThinkingPanel";
import { ToolButtons } from "./ToolButtons";

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
  const { displayText, pdfDownload } = parseMessageWithPdf(message.content);

  if (isUser && !message.content.trim()) {
    return null;
  }

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl bg-zinc-100 px-4 py-2.5 text-[15px] leading-relaxed text-zinc-900">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="text-[15px] leading-relaxed text-zinc-900">
      <div className="inline-flex items-start gap-2.5 max-w-full">
        <div className="min-w-0 space-y-2">
          {renderMarkdown(displayText, sources, onSourceClick)}
          {streaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-900 align-middle" />
          )}
        </div>
        {pdfDownload && !streaming && (
          <div className="shrink-0 pt-0.5">
            <PdfDownloadButton href={pdfDownload.href} filename={pdfDownload.filename} />
          </div>
        )}
      </div>
      {!streaming && sources.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-zinc-400 self-center mr-1">References:</span>
          {sources.map((source, idx) => (
            <CitationButton
              key={source.segment_id || idx}
              index={idx}
              title={source.title}
              onClick={() => onSourceClick(source, idx)}
            />
          ))}
        </div>
      )}
      {message.status === "failed" && <span className="mt-2 block text-xs text-rose-500">Failed</span>}
    </div>
  );
}

export function ConversationChatView({ scope }: { scope: ConversationScope }) {
  const { state, selectConversation } = useApp();
  const projectId = scope === "project" ? state.project?.projectId : undefined;
  const [conversationId, setConversationId] = useState<string | null>(state.activeConversationId);
  const [messages, setMessages] = useState<PersistedMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [selectedTool, setSelectedTool] = useState<ChatToolId | null>(null);
  const [sources, setSources] = useState<ConversationSource[]>([]);
  const [uploading, setUploading] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [agentOutputs, setAgentOutputs] = useState<AgentOutput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<{ source: SearchSource; index: number } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const funnyLines = [
    "Let's build something awesome (or just write code we'll rewrite later).",
    "Ready to look extremely productive while we over-analyze things?",
    "What conspiracy theories or complex code are we scrutinizing today?",
    "Ask me anything. I promise not to tell your boss.",
    "Let's solve some problems that probably didn't exist five minutes ago.",
    "Let's make today count. Or, you know, we can just ask AI to do it.",
  ];
  const [catchyLine] = useState(() => funnyLines[Math.floor(Math.random() * funnyLines.length)]);

  useEffect(() => {
    setConversationId(state.activeConversationId);
  }, [state.activeConversationId]);

  useEffect(() => {
    if (loading) return;

    if (!conversationId) {
      setMessages([]);
      setAgentOutputs([]);
      setSources([]);
      return;
    }

    fetchConversationMessages(conversationId)
      .then((result) => setMessages(result.messages))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Failed to load messages"));
    fetchConversationSources(conversationId)
      .then((result) => setSources(result.sources))
      .catch(() => setSources([]));
  }, [conversationId, loading]);

  useEffect(() => {
    if (!conversationId) return;
    const pending = sources.some((source) => source.status !== "indexed" && source.status !== "failed");
    if (!pending) return;
    const timer = window.setInterval(() => {
      fetchConversationSources(conversationId)
        .then((result) => setSources(result.sources))
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [conversationId, sources]);

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

  async function ensureConversationId(): Promise<string> {
    if (conversationId) return conversationId;
    const created = await createConversation(scope, projectId);
    setConversationId(created.id);
    selectConversation(created.id, scope === "general" ? "general-chat" : "project");
    notifyConversationListChanged();
    return created.id;
  }

  async function handleAttach(file: File) {
    if (uploading) return;
    setUploading(true);
    setError(null);
    try {
      const id = await ensureConversationId();
      await uploadConversationSource(id, file);
      const result = await fetchConversationSources(id);
      setSources(result.sources);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function toggleTool(toolId: ChatToolId) {
    if (loading) return;
    setSelectedTool((current) => (current === toolId ? null : toolId));
  }

  async function runStream(
    content: string,
    options?: { requestedTool?: string; silentUserMessage?: boolean },
  ) {
    setLoading(true);
    setError(null);
    setStreamingText("");
    setAgentOutputs([]);

    const clientMessageId = crypto.randomUUID();
    if (!options?.silentUserMessage) {
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
    }

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
        console.log("ConversationChatView SSE Event:", event);
        if (event.event === "message.accepted" && event.data.user_message) {
          if (options?.silentUserMessage) {
            return;
          }
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
          setMessages((current) => [
            ...current.filter((message) => message.id !== event.data.assistant_message.id),
            event.data.assistant_message,
          ]);
          setStreamingText("");
          notifyConversationListChanged();
        }
        if (event.event === "error") setError(event.data.message);
      }, {
        requestedTool: options?.requestedTool,
        webSearchMode: state.search.webSearchMode,
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

  async function submit() {
    const content = draft.trim();
    if (!content || loading) return;
    const requestedTool = selectedTool
      ? CHAT_TOOLS.find((entry) => entry.id === selectedTool)?.requestedTool
      : undefined;
    setDraft("");
    setSelectedTool(null);
    await runStream(content, requestedTool ? { requestedTool } : undefined);
  }

  const active = messages.some((message) => message.role === "user" && message.content.trim()) || Boolean(conversationId);
  const composerDocked = active || loading;
  const contextLabel = scope === "general" ? "Web chat" : state.project?.projectName ?? "Project chat";
  const inputProps = {
    value: draft,
    onChange: setDraft,
    onSubmit: () => void submit(),
    onAttach: (file: File) => {
      void handleAttach(file);
    },
    attachments: sources,
    attachDisabled: uploading || !state.apiConnected,
    loading,
    disabled: !state.apiConnected,
    webOnly: scope === "general",
  };
  const toolButtons = (
    <ToolButtons
      selectedTool={selectedTool}
      disabled={!state.apiConnected || loading}
      onSelect={toggleTool}
    />
  );
  const attachmentChips = sources.length > 0 && (
    <div className="mb-2 flex flex-wrap gap-2">
      {sources.map((source) => (
        <span
          key={source.file_id}
          className="inline-flex items-center gap-1.5 rounded-full border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] px-2.5 py-1 text-xs text-[var(--app-text-soft)]"
          title={source.filename}
        >
          <span className="max-w-[12rem] truncate">{source.filename}</span>
          <span className="text-[10px] uppercase tracking-wide opacity-70">{source.status}</span>
        </span>
      ))}
    </div>
  );

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
        <div className="mb-8 max-w-2xl px-4 text-center">
          <span className="mb-4 inline-flex rounded-full bg-black/5 px-3 py-1 text-xs font-semibold text-zinc-500 dark:bg-white/5 dark:text-zinc-400">
            {contextLabel}
          </span>
          <h1 className="text-3xl font-bold leading-tight tracking-tight text-[var(--app-text)] sm:text-4xl">
            {catchyLine}
          </h1>
        </div>
        <div className="flex w-full max-w-3xl flex-col items-center">
          {attachmentChips}
          <ChatInput {...inputProps} />
          <div className="pt-3">
            {toolButtons}
          </div>
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
          composerDocked ? "chat-dock-enter max-h-[22rem]" : "max-h-0 overflow-hidden pb-0 pt-0 opacity-0"
        }`}
      >
        <div className="mx-auto w-full max-w-3xl">
          {attachmentChips}
          <ThinkingPanel outputs={agentOutputs} loading={loading} />
          <div className="pt-2">
            <ChatInput {...inputProps} />
          </div>
          <div className="pt-3">
            {toolButtons}
          </div>
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
