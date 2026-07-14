import { useState } from "react";
import { fetchPdfBlob } from "../api/client";
import { IconDownload } from "./icons";

export function PdfDownloadButton({
  href,
  filename,
}: {
  href: string;
  filename: string;
}) {
  const [downloading, setDownloading] = useState(false);

  async function handleDownload() {
    if (downloading) return;
    setDownloading(true);
    try {
      const blob = await fetchPdfBlob(href);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      console.error("PDF download failed:", error);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <button
      type="button"
      onClick={() => void handleDownload()}
      disabled={downloading}
      title={downloading ? "Downloading PDF..." : "Download PDF"}
      aria-label={downloading ? "Downloading PDF" : "Download PDF"}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] text-[var(--app-text-soft)] transition-colors hover:bg-[var(--app-bg-glass)] hover:text-[var(--app-text)] disabled:opacity-60"
    >
      <IconDownload className={`h-4 w-4 ${downloading ? "animate-pulse" : ""}`} />
    </button>
  );
}
