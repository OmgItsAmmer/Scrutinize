import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  fetchConversationMessages,
  streamConversationMessage,
} from "../api/client";
import { useApp } from "../context/AppContext";
import type { ConversationScope, PersistedMessage } from "../types/api";
import { ChatInput } from "./ChatInput";

export function ConversationChatView({ scope }: { scope: ConversationScope }) {
  const { state, selectConversation } = useApp();
  const projectId = scope === "project" ? state.project?.projectId : undefined;
  const [conversationId, setConversationId] = useState<string | null>(state.activeConversationId);
  const [messages, setMessages] = useState<PersistedMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setConversationId(state.activeConversationId);
  }, [state.activeConversationId]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
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
    try {
      let id = conversationId;
      if (!id) {
        const created = await createConversation(scope, projectId);
        id = created.id;
        setConversationId(id);
        selectConversation(id, scope === "general" ? "general-chat" : "project");
        notifyConversationListChanged();
      }
      const optimistic: PersistedMessage = {
        id: crypto.randomUUID(), conversation_id: id, role: "user", content,
        status: "completed", citations: [], created_at: new Date().toISOString(), completed_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, optimistic]);
      await streamConversationMessage(id, content, crypto.randomUUID(), (event) => {
        if (event.event === "status") setStatus(event.data.label);
        if (event.event === "delta") setStreamingText((current) => current + event.data.text);
        if (event.event === "message.completed") {
          setMessages((current) => [...current, event.data.assistant_message]);
          setStreamingText("");
          setStatus(null);
          notifyConversationListChanged();
        }
        if (event.event === "error") setError(event.data.message);
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Message failed");
    } finally {
      setLoading(false);
      setStatus(null);
    }
  }

  const active = messages.length > 0 || Boolean(conversationId);
  const contextLabel = scope === "general" ? "Web chat" : state.project?.projectName ?? "Project chat";

  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--app-chat-bg)]">
      <div className={`min-h-0 flex-1 overflow-y-auto px-4 ${active ? "py-5" : "flex items-center"}`}>
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-end gap-2">
          {!active && (
            <div className="mb-8 text-center">
              <span className="inline-flex rounded-full bg-black/5 px-3 py-1 text-xs font-medium text-zinc-600">
                {contextLabel}
              </span>
              <p className="mt-3 text-sm text-zinc-500">Start a new conversation from the box below.</p>
            </div>
          )}
          {messages.filter((message) => message.role !== "system").map((message) => (
            <article
              key={message.id}
              className={
                message.role === "user"
                  ? "ml-auto max-w-[76%] rounded-lg rounded-tr-sm border border-[var(--app-border)] bg-[var(--app-chat-user)] px-3 py-2 text-sm leading-6 text-[var(--app-text)] shadow-sm backdrop-blur-xl"
                  : "mr-auto max-w-[76%] rounded-lg rounded-tl-sm border border-[var(--app-border)] bg-[var(--app-chat-assistant)] px-3 py-2 text-sm leading-6 text-[var(--app-text)] shadow-sm backdrop-blur-xl"
              }
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.status === "failed" && <span className="mt-2 block text-xs text-rose-500">Failed</span>}
            </article>
          ))}
          {streamingText && (
            <article className="mr-auto max-w-[76%] rounded-lg rounded-tl-sm border border-[var(--app-border)] bg-[var(--app-chat-assistant)] px-3 py-2 text-sm leading-6 text-[var(--app-text)] shadow-sm backdrop-blur-xl">
              <p className="whitespace-pre-wrap">{streamingText}</p>
            </article>
          )}
          {status && <p className="animate-pulse px-1 text-xs text-zinc-500">{status}...</p>}
          {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div ref={endRef} />
        </div>
      </div>
      <div className="shrink-0 border-t border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] px-4 pb-3 pt-3 backdrop-blur-3xl">
        <div className="mx-auto w-full max-w-3xl">
          <ChatInput value={draft} onChange={setDraft} onSubmit={() => void submit()} loading={loading} disabled={!state.apiConnected} webOnly={scope === "general"} />
        </div>
      </div>
    </div>
  );
}
