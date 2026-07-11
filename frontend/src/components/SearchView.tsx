import { useEffect, useRef, useState } from "react";
import { useApp } from "../context/AppContext";
import { ChatInput } from "./ChatInput";
import { ModalityChips } from "./ModalityChips";
import { ThinkingPanel } from "./ThinkingPanel";
import { ScrollFade, SourceCard, renderMarkdown, SourcePreviewModal } from "./SourceCard";
import type { SearchSource } from "../types/api";
import { IconDownload, IconX } from "./icons";

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
  onLinkClick,
}: {
  content: string;
  streaming?: boolean;
  sources?: SearchSource[];
  onSourceClick?: (source: SearchSource, index: number) => void;
  onLinkClick?: (href: string) => void;
}) {
  return (
    <div className="text-[15px] leading-relaxed text-zinc-900">
      <div className="space-y-2">{renderMarkdown(content, sources, onSourceClick, onLinkClick)}</div>
      {streaming && (
        <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-900 align-middle" />
      )}
    </div>
  );
}

function PdfPanel({
  open,
  url,
  title,
  filename,
  onClose,
}: {
  open: boolean;
  url: string | null;
  title: string | null;
  filename: string | null;
  onClose: () => void;
}) {
  return (
    <aside
      className={`hidden min-h-0 w-[min(42vw,36rem)] shrink-0 flex-col border-l border-white/60 bg-white/20 backdrop-blur-3xl saturate-150 transition-all duration-500 lg:flex ${
        open ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-4 opacity-0"
      }`}
    >
      <div className="border-b border-white/40 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">
              PDF Preview
            </p>
            <h2 className="mt-1 truncate text-base font-semibold text-zinc-950">
              {filename ?? "generated-document.pdf"}
            </h2>
            {title && <p className="mt-1 line-clamp-2 text-sm text-zinc-600">{title}</p>}
          </div>
          <div className="flex items-center gap-2">
            {url && (
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-white/45 bg-white/65 px-3 py-2 text-xs font-semibold text-zinc-800 shadow-sm transition hover:bg-white"
              >
                <IconDownload className="h-3.5 w-3.5" />
                Open
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-white/45 bg-white/65 p-2 text-zinc-600 shadow-sm transition hover:bg-white hover:text-zinc-950"
              aria-label="Close PDF preview"
            >
              <IconX className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 p-4">
        <div className="flex h-full flex-col overflow-hidden rounded-[2rem] border border-white/60 bg-white/20 shadow-[0_20px_60px_rgba(15,23,42,0.05)] backdrop-blur-xl">
          {url ? (
            <iframe
              title={filename ?? "generated-document.pdf"}
              src={url}
              className="h-full w-full bg-white"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-zinc-500">
              No PDF available yet.
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

export function SearchView() {
  const { state, setSearchQuery, setModalityFilter, runSearch, openPdfDrawer, closePdfDrawer } = useApp();
  const { search, apiConnected } = state;
  const feedEndRef = useRef<HTMLDivElement>(null);
  const [activeSource, setActiveSource] = useState<{ source: SearchSource; index: number } | null>(null);

  const sessionActive =
    search.loading ||
    search.conversation.messages.length > 0 ||
    Boolean(search.result) ||
    Boolean(search.error);

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

  useEffect(() => {
    const answer = search.result?.answer ?? "";
    const match = answer.match(/\[([^\]]+)\]\(([^)]+\/v2\/pdf\/download\/[^)]+)\)/);
    if (!match) {
      return;
    }

    const url = match[2];
    const filename = url.split("/").filter(Boolean).pop() ?? "generated-document.pdf";
    openPdfDrawer({
      url,
      title: search.result?.query ?? "Generated PDF",
      filename,
    });
  }, [openPdfDrawer, search.result]);

  function handleSubmit() {
    void runSearch();
  }

  function handlePdfLinkClick(href: string) {
    if (!href.includes("/v2/pdf/download/")) {
      window.open(href, "_blank", "noopener,noreferrer");
      return;
    }

    const filename = href.split("/").filter(Boolean).pop() ?? "generated-document.pdf";
    openPdfDrawer({
      url: href,
      title: search.result?.query ?? "Generated PDF",
      filename,
    });
  }

  const inputProps = {
    value: search.query,
    onChange: setSearchQuery,
    onSubmit: handleSubmit,
    disabled: !apiConnected,
    loading: search.loading,
    showNewSession: sessionActive,
  };

  const thinkingPanel = <ThinkingPanel outputs={search.agentOutputs} loading={search.loading} />;

  const pdfOpen = state.pdfDrawer.open && Boolean(state.pdfDrawer.url);

  return (
    <div className="flex h-full min-w-0 flex-row bg-[var(--chatly-bg)]">
      <div className={`relative flex min-w-0 flex-1 flex-col transition-all duration-500 ${pdfOpen ? "lg:max-w-[58%]" : ""}`}>
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
                  onLinkClick={handlePdfLinkClick}
                />
              ),
            )}

            {search.loading && search.activeQuery && <UserMessage content={search.activeQuery} />}

            {search.loading && search.realtimeText && (
              <AssistantMessage
                content={search.realtimeText}
                streaming
                sources={search.realtimeSources || []}
                onSourceClick={(source, idx) => setActiveSource({ source, index: idx })}
                onLinkClick={handlePdfLinkClick}
              />
            )}

            {search.error && <p className="text-sm text-rose-600">{search.error}</p>}

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

        <div
          className={`shrink-0 overflow-visible px-4 transition-all duration-500 ease-out sm:px-6 ${
            sessionActive
              ? "chat-dock-enter max-h-[28rem] py-3 sm:max-h-[32rem] sm:py-4"
              : "max-h-0 overflow-hidden py-0 opacity-0"
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

      <PdfPanel
        open={pdfOpen}
        url={state.pdfDrawer.url}
        title={state.pdfDrawer.title}
        filename={state.pdfDrawer.filename}
        onClose={closePdfDrawer}
      />

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
