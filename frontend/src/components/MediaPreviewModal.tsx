import { useEffect, useMemo, useState } from "react";
import { libraryFileContentUrl } from "../api/client";
import type { FileModality, LibraryFileItem } from "../types/api";
import { IconDocument, IconDownload, IconFilm, IconWaveform, IconX } from "./icons";

type MediaPreviewModalProps = {
  file: LibraryFileItem;
  onClose: () => void;
};

function ModalityIcon({ modality, className }: { modality: FileModality; className?: string }) {
  if (modality === "video") {
    return <IconFilm className={className} />;
  }
  if (modality === "audio") {
    return <IconWaveform className={className} />;
  }
  return <IconDocument className={className} />;
}

function TextPreview({ url }: { url: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadText() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to load file (${response.status})`);
        }
        const text = await response.text();
        if (text.includes("@react-refresh") && text.includes("/@vite/client")) {
          throw new Error("Received an invalid preview response. Try refreshing the library.");
        }
        if (!cancelled) {
          setContent(text);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load text");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadText();
    return () => {
      cancelled = true;
    };
  }, [url]);

  if (loading) {
    return <p className="text-sm text-zinc-500">Loading text…</p>;
  }
  if (error) {
    return <p className="text-sm text-rose-600">{error}</p>;
  }
  return (
    <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-xl bg-zinc-50 p-4 text-sm leading-relaxed text-zinc-800">
      {content}
    </pre>
  );
}

function MediaError({ message }: { message: string }) {
  return <p className="text-sm text-rose-600">{message}</p>;
}

export function MediaPreviewModal({ file, onClose }: MediaPreviewModalProps) {
  const previewUrl = useMemo(() => libraryFileContentUrl(file.id), [file.id]);
  const downloadUrl = useMemo(() => libraryFileContentUrl(file.id, true), [file.id]);
  const [mediaError, setMediaError] = useState<string | null>(null);

  useEffect(() => {
    setMediaError(null);
  }, [file.id]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-zinc-900/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative w-full max-h-[92dvh] max-w-3xl overflow-hidden rounded-t-2xl border border-zinc-200 bg-white shadow-xl sm:max-h-none sm:rounded-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="media-preview-title"
      >
        <div className="flex items-center justify-between gap-3 border-b border-zinc-100 px-4 py-3 sm:gap-4 sm:px-5 sm:py-4">
          <div className="min-w-0">
            <h2 id="media-preview-title" className="truncate text-base font-semibold text-zinc-900">
              {file.filename}
            </h2>
            <p className="text-xs capitalize text-zinc-500">{file.modality}</p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={downloadUrl}
              download={file.filename}
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-50"
            >
              <IconDownload className="h-3.5 w-3.5" />
              Download
            </a>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-2 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-800"
              aria-label="Close preview"
            >
              <IconX className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="overflow-y-auto p-4 sm:p-5">
          {file.modality === "video" && (
            <>
              {mediaError ? (
                <MediaError message={mediaError} />
              ) : (
                <video
                  key={previewUrl}
                  controls
                  autoPlay
                  className="max-h-[60vh] w-full rounded-xl bg-black"
                  src={previewUrl}
                  onError={() => setMediaError("Unable to play this video. Try downloading it instead.")}
                />
              )}
            </>
          )}
          {file.modality === "audio" && (
            <div className="flex flex-col items-center gap-4 py-8">
              <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
                <IconWaveform className="h-10 w-10" />
              </div>
              {mediaError ? (
                <MediaError message={mediaError} />
              ) : (
                <audio
                  key={previewUrl}
                  controls
                  autoPlay
                  className="w-full"
                  src={previewUrl}
                  onError={() => setMediaError("Unable to play this audio. Try downloading it instead.")}
                />
              )}
            </div>
          )}
          {file.modality === "text" && <TextPreview url={previewUrl} />}
          {file.modality !== "text" && file.modality !== "audio" && file.modality !== "video" && (
            <div className="flex flex-col items-center gap-3 py-10 text-zinc-500">
              <ModalityIcon modality={file.modality} className="h-12 w-12" />
              <p className="text-sm">Preview not available for this file type.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
