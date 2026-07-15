import { useState } from "react";
import { Viewer, Worker } from "@react-pdf-viewer/core";
import "@react-pdf-viewer/core/lib/styles/index.css";

// Import styles and components from @react-pdf-viewer/core
interface PdfViewerProps {
  fileUrl: string;
}

export function PdfViewer({ fileUrl }: PdfViewerProps) {
  const [zoom, setZoom] = useState<number>(1.0);
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  const handleDocumentLoad = (e: { doc: { numPages: number } }) => {
    setNumPages(e.doc.numPages);
    setLoading(false);
  };

  const handlePageChange = (e: { currentPage: number }) => {
    setCurrentPage(e.currentPage);
  };

  const zoomIn = () => setZoom((prev) => Math.min(prev + 0.2, 2.5));
  const zoomOut = () => setZoom((prev) => Math.max(prev - 0.2, 0.6));

  return (
    <div className="my-4 flex flex-col overflow-hidden rounded-2xl border border-zinc-200/50 bg-white/40 shadow-sm backdrop-blur-md dark:border-zinc-800/50 dark:bg-zinc-950/20 w-full animate-fade-in transition-all">
      {/* Control bar */}
      <div className="flex items-center justify-between border-b border-zinc-200/50 bg-white/60 px-4 py-2.5 dark:border-zinc-800/50 dark:bg-zinc-950/40">
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-900/35 dark:text-blue-300">
            PDF Preview
          </span>
          {!loading && (
            <span className="text-[11px] font-bold text-zinc-500 dark:text-zinc-400">
              Page {currentPage + 1} of {numPages}
            </span>
          )}
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={zoomOut}
            className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition hover:bg-zinc-50 hover:-translate-y-0.5 active:translate-y-0 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
            title="Zoom Out"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 12H6" />
            </svg>
          </button>
          <span className="text-xs font-bold text-zinc-600 dark:text-zinc-300 w-11 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={zoomIn}
            className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition hover:bg-zinc-50 hover:-translate-y-0.5 active:translate-y-0 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
            title="Zoom In"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          </button>
        </div>
      </div>

      {/* PDF Document Viewer Container */}
      <div className="relative min-h-[300px] max-h-[500px] w-full overflow-y-auto p-4 bg-zinc-50/50 dark:bg-zinc-900/20">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-zinc-950/80 z-10">
            <div className="flex flex-col items-center gap-3">
              <svg className="h-8 w-8 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">Loading document...</span>
            </div>
          </div>
        )}

        <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js">
          <div className="mx-auto max-w-full origin-top transition-transform duration-200" style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}>
            <Viewer
              fileUrl={fileUrl}
              onDocumentLoad={handleDocumentLoad}
              onPageChange={handlePageChange}
            />
          </div>
        </Worker>
      </div>
    </div>
  );
}
