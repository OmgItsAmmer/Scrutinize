import { useEffect, useRef, useState } from "react";
import { useApp } from "../context/AppContext";
import { ChatInput } from "./ChatInput";
import { ModalityChips } from "./ModalityChips";
import { ThinkingPanel } from "./ThinkingPanel";
import { ScrollFade, SourceCard, renderMarkdown, SourcePreviewModal } from "./SourceCard";
import type { SearchSource } from "../types/api";

const CHAT_INPUT_WIDTH = "max-w-3xl";
const CHAT_FEED_WIDTH = "max-w-3xl";

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl bg-zinc-100 px-4 py-2.5 text-[15px] leading-relaxed text-zinc-900">
        {content}
      </div>
    </div>
  );
}

function AssistantMessage({
  content,
  streaming = false,
  sources = [],
  onSourceClick,
}: {
  content: string;
  streaming?: boolean;
  sources?: SearchSource[];
  onSourceClick?: (source: SearchSource, index: number) => void;
}) {
  return (
    <div className="text-[15px] leading-relaxed text-zinc-900">
      <div className="space-y-2">{renderMarkdown(content, sources, onSourceClick)}</div>
      {streaming && (
        <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-900 align-middle" />
      )}
    </div>
  );
}

export function SearchView() {
  const { state, setSearchQuery, setModalityFilter, runSearch } = useApp();
  const { search, apiConnected } = state;
  const feedEndRef = useRef<HTMLDivElement>(null);
  const [activeSource, setActiveSource] = useState<{ source: SearchSource; index: number } | null>(null);

  const sessionActive =
    search.loading ||
    search.conversation.messages.length > 0 ||
    Boolean(search.result) ||
    Boolean(search.error);

  const showSources =
    (search.result && search.result.sources.length > 0) ||
    (search.loading && search.realtimeSources && search.realtimeSources.length > 0);

  useEffect(() => {
    if (!sessionActive) return;
    feedEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [
    sessionActive,
    search.conversation.messages.length,
    search.activeQuery,
    search.realtimeText,
    search.loading,
    search.agentOutputs.length,
  ]);

  function handleSubmit() {
    void runSearch();
  }

  const inputProps = {
    value: search.query,
    onChange: setSearchQuery,
    onSubmit: handleSubmit,
    disabled: !apiConnected,
    loading: search.loading,
    showNewSession: sessionActive,
  };

  const thinkingPanel = (
    <ThinkingPanel outputs={search.agentOutputs} loading={search.loading} />
  );

  return (
    <div className="flex h-full flex-row bg-[var(--chatly-bg)]">
      <div className="relative flex min-w-0 flex-1 flex-col">
        {/* Hero + centered input (initial state) */}
        <div
          className={`absolute inset-0 z-10 flex flex-col items-center justify-center px-4 pb-4 transition-all duration-500 ease-out sm:px-6 sm:pb-8 ${
            sessionActive
              ? "pointer-events-none translate-y-[-1.5rem] opacity-0"
              : "translate-y-0 opacity-100"
          }`}
          aria-hidden={sessionActive}
        >
          <div className={`mb-6 w-full ${CHAT_INPUT_WIDTH} text-center sm:mb-10`}>
            <h1 className="text-2xl font-bold leading-tight tracking-tight text-[var(--chatly-text-primary)] sm:text-[2rem] md:text-[2.5rem]">
              Hey, What&apos;s on your mind today?
            </h1>
          </div>

          <div className={`w-full ${CHAT_INPUT_WIDTH} space-y-4 sm:space-y-5`}>
            <ChatInput {...inputProps} />
            <ModalityChips
              value={search.modalityFilter}
              onChange={setModalityFilter}
              disabled={!apiConnected || search.loading}
            />
          </div>
        </div>

        {/* Message feed */}
        <div
          className={`flex min-h-0 flex-1 flex-col overflow-y-auto px-4 transition-opacity duration-500 ease-out sm:px-6 ${
            sessionActive ? "opacity-100" : "pointer-events-none opacity-0"
          } no-scrollbar`}
        >
          <div className={`mx-auto w-full ${CHAT_FEED_WIDTH} flex-1 space-y-6 py-6 sm:space-y-8 sm:py-8`}>
            {search.conversation.messages.map((message, index) =>
              message.role === "user" ? (
                <UserMessage key={`${index}-user`} content={message.content} />
              ) : (
                <AssistantMessage
                  key={`${index}-assistant`}
                  content={message.content}
                  sources={search.result?.sources || []}
                  onSourceClick={(source, idx) => setActiveSource({ source, index: idx })}
                />
              ),
            )}

            {search.loading && search.activeQuery && (
              <UserMessage content={search.activeQuery} />
            )}

            {search.loading && search.realtimeText && (
              <AssistantMessage
                content={search.realtimeText}
                streaming
                sources={search.realtimeSources || []}
                onSourceClick={(source, idx) => setActiveSource({ source, index: idx })}
              />
            )}

            {search.error && (
              <p className="text-sm text-rose-600">{search.error}</p>
            )}

            {search.loading && search.realtimeSources && search.realtimeSources.length > 0 && (
              <div className="block lg:hidden">
                <h2 className="mb-3 text-sm font-semibold text-zinc-900">Sources</h2>
                <div className="space-y-3">
                  {search.realtimeSources.map((source, index) => (
                    <ScrollFade key={source.segment_id} delay={index * 150}>
                      <SourceCard source={source} index={index} />
                    </ScrollFade>
                  ))}
                </div>
              </div>
            )}

            {search.result && !search.loading && search.result.sources.length > 0 && (
              <div className="block lg:hidden">
                <h2 className="mb-3 text-sm font-semibold text-zinc-900">Sources</h2>
                <div className="space-y-3">
                  {search.result.sources.map((source, index) => (
                    <ScrollFade key={source.segment_id} delay={index * 150}>
                      <SourceCard source={source} index={index} />
                    </ScrollFade>
                  ))}
                </div>
              </div>
            )}

            <div ref={feedEndRef} />
          </div>
        </div>

        {/* Bottom dock */}
        <div
          className={`shrink-0 overflow-visible px-4 transition-all duration-500 ease-out sm:px-6 ${
            sessionActive
              ? "chat-dock-enter max-h-[28rem] py-3 sm:max-h-[32rem] sm:py-4"
              : "max-h-0 py-0 opacity-0 overflow-hidden"
          }`}
        >
          <div className={`relative mx-auto w-full ${CHAT_INPUT_WIDTH} space-y-3`}>
            {thinkingPanel}
            <ChatInput {...inputProps} />
            <ModalityChips
              value={search.modalityFilter}
              onChange={setModalityFilter}
              disabled={!apiConnected || search.loading}
            />
          </div>
        </div>
      </div>

      {showSources && (
        <div className="hidden w-80 shrink-0 overflow-y-auto p-6 no-scrollbar lg:block">
          <h2 className="mb-4 text-sm font-semibold text-zinc-900">Sources</h2>
          <div className="space-y-4">
            {(search.result?.sources || search.realtimeSources || []).map((source, index) => (
              <ScrollFade key={source.segment_id} delay={index * 150}>
                <SourceCard source={source} index={index} />
              </ScrollFade>
            ))}
          </div>
        </div>
      )}

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
