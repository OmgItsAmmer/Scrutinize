import { useEffect, useRef, useState } from "react";
import { fetchPdfBlob } from "../api/client";
import { useApp } from "../context/AppContext";
import { ChatInput } from "./ChatInput";
import { ModalityChips } from "./ModalityChips";
import { ThinkingPanel } from "./ThinkingPanel";
import { ScrollFade, SourceCard, renderMarkdown, SourcePreviewModal } from "./SourceCard";
import type { SearchSource } from "../types/api";
import { IconDownload, IconX } from "./icons";

const CHAT_INPUT_WIDTH = "max-w-3xl";
const CHAT_FEED_WIDTH = "max-w-3xl";

function filenameFromPdfUrl(url: string) {
  let name = url.split("?")[0]?.split("/").filter(Boolean).pop() ?? "generated-document.pdf";
  if (!name.endsWith(".pdf")) {
    name = `${name}.pdf`;
  }
  return name;
}

function pdfPreviewUrl(url: string) {
  let preview = url.replace("/v2/pdf/download/", "/v2/pdf/preview/").split("?")[0] ?? url;
  if (preview.endsWith(".pdf")) {
    preview = preview.slice(0, -4);
  }
  return preview;
}

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
  const previewUrl = url ? pdfPreviewUrl(url) : null;
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!previewUrl || !open) {
      setBlobUrl(null);
      setPdfBlob(null);
      setPreviewError(null);
      setPreviewLoading(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    setPreviewLoading(true);
    setPreviewError(null);
    setBlobUrl(null);
    setPdfBlob(null);

    fetchPdfBlob(previewUrl)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPdfBlob(blob);
        setBlobUrl(objectUrl);
      })
      .catch((error) => {
        if (cancelled) return;
        setPreviewError(error instanceof Error ? error.message : "Unable to load PDF preview.");
      })
      .finally(() => {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [open, previewUrl]);

  function handleDownload() {
    if (!pdfBlob) return;
    const objectUrl = URL.createObjectURL(pdfBlob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename ?? "generated-document.pdf";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  }

  return (
    <aside
      className={`hidden min-h-0 flex-1 flex-col border-l border-zinc-200/70 bg-white/70 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-2xl saturate-150 transition-all duration-500 lg:flex ${
        open ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-4 opacity-0"
      }`}
    >
      <div className="shrink-0 border-b border-zinc-200/70 px-4 py-3">
        <div className="flex min-h-12 items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              PDF Preview
            </p>
            <h2 className="mt-1 truncate text-base font-semibold text-zinc-950">
              {filename ?? "generated-document.pdf"}
            </h2>
            {title && <p className="mt-0.5 truncate text-xs text-zinc-500">{title}</p>}
          </div>
          <div className="flex items-center gap-2">
            {previewUrl && (
              <button
                type="button"
                onClick={handleDownload}
                disabled={!pdfBlob}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-200 bg-white text-zinc-700 shadow-sm transition hover:bg-zinc-50 hover:text-zinc-950"
                title="Download PDF"
                aria-label="Download PDF"
              >
                <IconDownload className="h-4 w-4" />
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-200 bg-white text-zinc-600 shadow-sm transition hover:bg-zinc-50 hover:text-zinc-950"
              aria-label="Close PDF preview"
              title="Close preview"
            >
              <IconX className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 bg-zinc-100">
        {previewLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            Loading PDF preview...
          </div>
        ) : previewError ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-rose-600">
            {previewError}
          </div>
        ) : blobUrl ? (
          <iframe
            title={filename ?? "generated-document.pdf"}
            src={blobUrl}
            className="h-full w-full bg-white"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            No PDF available yet.
          </div>
        )}
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

    const url = pdfPreviewUrl(match[2]);
    const filename = filenameFromPdfUrl(url);
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

    const url = pdfPreviewUrl(href);
    const filename = filenameFromPdfUrl(url);
    openPdfDrawer({
      url,
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
      <div className={`relative flex min-w-0 flex-col transition-all duration-500 ${pdfOpen ? "lg:w-[42%] lg:flex-none" : "flex-1"}`}>
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
