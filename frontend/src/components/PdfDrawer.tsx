import { useEffect, useMemo, useState } from "react";
import { fetchPdfBlob } from "../api/client";
import { useApp } from "../context/AppContext";
import { IconDownload, IconX } from "./icons";

function inferFilename(url: string | null, fallback: string | null) {
  if (fallback) return fallback;
  if (!url) return "generated.pdf";
  let last = "";
  try {
    const parsed = new URL(url);
    last = parsed.pathname.split("/").filter(Boolean).pop() || "generated.pdf";
  } catch {
    last = url.split("/").filter(Boolean).pop() || "generated.pdf";
  }
  if (!last.endsWith(".pdf")) {
    last = `${last}.pdf`;
  }
  return last;
}

function pdfPreviewUrl(url: string) {
  let preview = url.replace("/v2/pdf/download/", "/v2/pdf/preview/").split("?")[0] ?? url;
  if (preview.endsWith(".pdf")) {
    preview = preview.slice(0, -4);
  }
  return preview;
}

export function PdfDrawer() {
  const { state, closePdfDrawer } = useApp();
  const drawer = state.pdfDrawer;

  const filename = useMemo(
    () => inferFilename(drawer.url, drawer.filename),
    [drawer.filename, drawer.url],
  );
  const previewUrl = drawer.url ? pdfPreviewUrl(drawer.url) : null;
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!previewUrl || !drawer.open) {
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
  }, [drawer.open, previewUrl]);

  function handleDownload() {
    if (!pdfBlob) return;
    const objectUrl = URL.createObjectURL(pdfBlob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && drawer.open) {
        closePdfDrawer();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closePdfDrawer, drawer.open]);

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-zinc-950/20 backdrop-blur-sm transition-opacity duration-500 lg:block ${
          drawer.open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={closePdfDrawer}
        aria-hidden="true"
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-[44rem] flex-col border-l border-zinc-200/70 bg-white/75 shadow-[0_24px_80px_rgba(15,23,42,0.1)] backdrop-blur-2xl saturate-150 transition-all duration-500 ease-out ${
          drawer.open ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-full opacity-0"
        }`}
        aria-hidden={!drawer.open}
      >
        <div className="shrink-0 border-b border-zinc-200/70 px-5 py-4">
          <div className="flex min-h-12 items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                PDF Preview
              </p>
              <h2 className="mt-1 truncate text-lg font-semibold text-zinc-950">
                {filename}
              </h2>
              {drawer.title && (
                <p className="mt-0.5 truncate text-xs text-zinc-500">{drawer.title}</p>
              )}
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
                onClick={closePdfDrawer}
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
            <iframe title={filename} src={blobUrl} className="h-full w-full bg-white" />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-zinc-500">
              No PDF selected.
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
