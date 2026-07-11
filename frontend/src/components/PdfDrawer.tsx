import { useEffect, useMemo } from "react";
import { useApp } from "../context/AppContext";
import { IconDownload, IconX } from "./icons";

function inferFilename(url: string | null, fallback: string | null) {
  if (fallback) return fallback;
  if (!url) return "generated.pdf";
  try {
    const parsed = new URL(url);
    const last = parsed.pathname.split("/").filter(Boolean).pop();
    return last || "generated.pdf";
  } catch {
    const last = url.split("/").filter(Boolean).pop();
    return last || "generated.pdf";
  }
}

export function PdfDrawer() {
  const { state, closePdfDrawer } = useApp();
  const drawer = state.pdfDrawer;

  const filename = useMemo(
    () => inferFilename(drawer.url, drawer.filename),
    [drawer.filename, drawer.url],
  );

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
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-[34rem] flex-col border-l border-white/60 bg-white/20 shadow-[0_24px_80px_rgba(15,23,42,0.1)] backdrop-blur-3xl saturate-150 transition-all duration-500 ease-out ${
          drawer.open ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-full opacity-0"
        }`}
        aria-hidden={!drawer.open}
      >
        <div className="border-b border-white/40 px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                PDF Preview
              </p>
              <h2 className="mt-1 truncate text-lg font-semibold text-zinc-950">
                {filename}
              </h2>
              {drawer.title && (
                <p className="mt-1 line-clamp-2 text-sm text-zinc-600">{drawer.title}</p>
              )}
            </div>

            <button
              type="button"
              onClick={closePdfDrawer}
              className="rounded-full border border-white/40 bg-white/70 p-2 text-zinc-600 shadow-sm transition hover:bg-white hover:text-zinc-950"
              aria-label="Close PDF preview"
            >
              <IconX className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          <div className="flex h-full flex-col overflow-hidden rounded-[2rem] border border-white/60 bg-white/20 shadow-[0_12px_40px_rgba(0,0,0,0.03)] backdrop-blur-xl">
            <div className="flex items-center justify-between gap-3 border-b border-white/40 px-4 py-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">
                  Document
                </p>
                <p className="text-sm font-medium text-zinc-800">{filename}</p>
              </div>
              {drawer.url && (
                <a
                  href={drawer.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full bg-zinc-950 px-3 py-2 text-xs font-semibold text-white shadow-lg shadow-zinc-950/20 transition hover:-translate-y-[1px] hover:bg-zinc-800"
                >
                  <IconDownload className="h-3.5 w-3.5" />
                  Open PDF
                </a>
              )}
            </div>

            <div className="min-h-0 flex-1 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.8),rgba(248,248,250,0.95))] p-3">
              {drawer.url ? (
                <iframe
                  title={filename}
                  src={drawer.url}
                  className="h-full w-full rounded-[1.5rem] border border-white/40 bg-white shadow-[0_10px_40px_rgba(15,23,42,0.08)]"
                />
              ) : (
                <div className="flex h-full items-center justify-center rounded-[1.5rem] border border-dashed border-zinc-300 bg-white/60 text-sm text-zinc-500">
                  No PDF selected.
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
