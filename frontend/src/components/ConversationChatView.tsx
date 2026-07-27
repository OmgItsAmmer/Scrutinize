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
  pdfPreviewUrl,
  type ChatToolId,
} from "../lib/chatTools";
import type { ConversationScope, PersistedMessage, SearchSource } from "../types/api";
import { ChatInput } from "./ChatInput";
import { PdfDownloadButton } from "./PdfDownloadButton";
import { renderMarkdown, SourcePreviewModal, CitationButton } from "./SourceCard";
import { ThinkingPanel } from "./ThinkingPanel";
import { ToolButtons } from "./ToolButtons";
import { PdfViewer } from "./PdfViewer";

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

function appendAssistantDelta(
  messages: PersistedMessage[],
  assistantMessageId: string,
  conversationId: string,
  text: string,
): PersistedMessage[] {
  const existing = messages.find((message) => message.id === assistantMessageId);
  if (existing) {
    return messages.map((message) =>
      message.id === assistantMessageId
        ? { ...message, content: message.content + text, status: "streaming" as const }
        : message,
    );
  }

  return [
    ...messages,
    {
      id: assistantMessageId,
      conversation_id: conversationId,
      role: "assistant",
      content: text,
      status: "streaming",
      citations: [],
      created_at: new Date().toISOString(),
      completed_at: null,
    },
  ];
}

function mergeMessagesPreservingLocalContent(
  local: PersistedMessage[],
  remote: PersistedMessage[],
): PersistedMessage[] {
  const localById = new Map(local.map((message) => [message.id, message]));

  return remote.map((remoteMessage) => {
    const localMessage = localById.get(remoteMessage.id);
    if (
      localMessage
      && localMessage.content.length > remoteMessage.content.length
      && (remoteMessage.status === "streaming" || remoteMessage.status === "pending" || !remoteMessage.content.trim())
    ) {
      return { ...remoteMessage, content: localMessage.content };
    }
    return remoteMessage;
  });
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
  const [showPdfPreview, setShowPdfPreview] = useState(false);
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

  if (!displayText.trim() && !streaming) {
    return null;
  }

  return (
    <div className="text-[15px] leading-relaxed text-zinc-900 w-full">
      <div className="flex items-start justify-between gap-3 w-full">
        <div className="min-w-0 flex-1 space-y-2">
          {renderMarkdown(displayText, sources, onSourceClick)}
          {streaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-900 align-middle" />
          )}
        </div>
        {pdfDownload && !streaming && (
          <div className="shrink-0 pt-0.5 flex flex-col gap-2">
            <PdfDownloadButton href={pdfDownload.href} filename={pdfDownload.filename} />
            <button
              type="button"
              onClick={() => setShowPdfPreview((prev) => !prev)}
              className={[
                "flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0",
                showPdfPreview
                  ? "border-blue-400 bg-blue-50 text-blue-600 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-400"
                  : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800",
              ].join(" ")}
              title={showPdfPreview ? "Hide Preview" : "Preview PDF"}
            >
              <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                {showPdfPreview ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.43 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                )}
              </svg>
            </button>
          </div>
        )}
      </div>

      {showPdfPreview && pdfDownload && !streaming && (
        <div className="w-full">
          <PdfViewer fileUrl={pdfPreviewUrl(pdfDownload.href)} />
        </div>
      )}

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
  const [agentOutputs, setAgentOutputs] = useState<AgentOutput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<{ source: SearchSource; index: number } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const activeStreamRef = useRef(0);
  const messagesRef = useRef<PersistedMessage[]>([]);
  const loadingRef = useRef(false);

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
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    setConversationId(state.activeConversationId);
  }, [state.activeConversationId]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setAgentOutputs([]);
      setSources([]);
      return;
    }
    if (loadingRef.current) {
      return;
    }

    let cancelled = false;
    fetchConversationMessages(conversationId)
      .then((result) => {
        if (!cancelled) setMessages(result.messages);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Failed to load messages");
      });
    fetchConversationSources(conversationId)
      .then((result) => {
        if (!cancelled) setSources(result.sources);
      })
      .catch(() => {
        if (!cancelled) setSources([]);
      });

    return () => {
      cancelled = true;
    };
  }, [conversationId]);

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
  }, [messages, loading]);

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

  async function refreshMessages(id: string, preserveLocalContent = false) {
    const result = await fetchConversationMessages(id);
    if (preserveLocalContent) {
      setMessages(mergeMessagesPreservingLocalContent(messagesRef.current, result.messages));
      return mergeMessagesPreservingLocalContent(messagesRef.current, result.messages);
    }
    setMessages(result.messages);
    return result.messages;
  }

  async function runStream(
    content: string,
    options?: { requestedTool?: string; silentUserMessage?: boolean },
  ) {
    const streamId = ++activeStreamRef.current;
    setLoading(true);
    setError(null);
    setAgentOutputs([]);

    const clientMessageId = crypto.randomUUID();
    let streamCompleted = false;
    let activeConversationId = conversationId;
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
      if (!activeConversationId) {
        const created = await createConversation(scope, projectId);
        activeConversationId = created.id;
        setConversationId(activeConversationId);
        selectConversation(activeConversationId, scope === "general" ? "general-chat" : "project");
        notifyConversationListChanged();
      }

      const { completed } = await streamConversationMessage(activeConversationId, content, clientMessageId, (event) => {
        if (streamId !== activeStreamRef.current) return;

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
          setMessages((current) =>
            appendAssistantDelta(
              current,
              event.data.assistant_message_id,
              activeConversationId!,
              event.data.text,
            ),
          );
          setAgentOutputs((current) => appendSynthesizerOutput(current, event.data.text));
        }
        if (event.event === "message.completed") {
          streamCompleted = true;
          setAgentOutputs((current) =>
            completeAgentOutput(current, "synthesis", null, event.data.assistant_message.content),
          );
          setMessages((current) => [
            ...current.filter((message) => message.id !== event.data.assistant_message.id),
            event.data.assistant_message,
          ]);
          notifyConversationListChanged();
        }
        if (event.event === "error") {
          setError(event.data.message);
        }
      }, {
        requestedTool: options?.requestedTool,
        webSearchMode: state.search.webSearchMode,
        useCloudLlm: state.search.model === "gpt-4o-mini",
      });
      streamCompleted = streamCompleted || completed;
    } catch (reason) {
      if (streamId === activeStreamRef.current) {
        setError(reason instanceof Error ? reason.message : "Message failed");
      }
    } finally {
      if (streamId !== activeStreamRef.current) return;

      setLoading(false);
      setAgentOutputs((current) =>
        current.map((entry) => (entry.status === "active" ? { ...entry, status: "complete" } : entry)),
      );

      if (!streamCompleted && activeConversationId) {
        try {
          await refreshMessages(activeConversationId, true);
          notifyConversationListChanged();
        } catch {
          // Keep locally streamed assistant content visible.
        }
      }
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
              streaming={message.status === "streaming" && loading}
              onSourceClick={(source, index) => setActiveSource({ source, index })}
            />
          ))}
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
