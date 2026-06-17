import { useState } from "react";
import { useApp } from "../context/AppContext";
import { formatDateTime, formatDurationSeconds } from "../lib/format";
import type { FileModality, FileStatus, LibraryFileItem } from "../types/api";
import { IconDocument, IconFilm, IconTrash, IconWaveform } from "./icons";
import { MediaPreviewModal } from "./MediaPreviewModal";

function statusBadge(status: FileStatus): string {
  switch (status) {
    case "indexed":
      return "bg-emerald-100 text-emerald-800";
    case "processing":
      return "bg-sky-100 text-sky-800";
    case "failed":
      return "bg-rose-100 text-rose-800";
    default:
      return "bg-zinc-100 text-zinc-700";
  }
}

function ThumbnailPlaceholder({ modality }: { modality: FileModality }) {
  const styles = {
    text: "bg-sky-100 text-sky-700",
    audio: "bg-violet-100 text-violet-700",
    video: "bg-amber-100 text-amber-700",
  }[modality];

  const Icon = modality === "video" ? IconFilm : modality === "audio" ? IconWaveform : IconDocument;

  return (
    <div
      className={`flex h-14 w-20 items-center justify-center rounded-lg border border-zinc-200 ${styles}`}
    >
      <Icon className="h-6 w-6" />
    </div>
  );
}

function FileThumbnail({ file, onClick }: { file: LibraryFileItem; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group overflow-hidden rounded-lg border border-zinc-200 transition hover:border-zinc-300 hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2"
      title={`Preview ${file.filename}`}
    >
      {file.thumbnail_url ? (
        <img
          src={file.thumbnail_url}
          alt={file.filename}
          className="h-14 w-20 object-cover transition group-hover:scale-105"
          loading="lazy"
        />
      ) : (
        <ThumbnailPlaceholder modality={file.modality} />
      )}
    </button>
  );
}

type LibraryItemProps = {
  file: LibraryFileItem;
  deleting: boolean;
  onPreview: (file: LibraryFileItem) => void;
  onDelete: (file: LibraryFileItem) => void;
};

function LibraryRow({ file, deleting, onPreview, onDelete }: LibraryItemProps) {
  return (
    <tr className="border-b border-zinc-100 last:border-0">
      <td className="px-4 py-3">
        <FileThumbnail file={file} onClick={() => onPreview(file)} />
      </td>
      <td className="px-4 py-3 text-sm font-medium text-zinc-900">{file.filename}</td>
      <td className="px-4 py-3 text-sm capitalize text-zinc-600">{file.modality}</td>
      <td className="px-4 py-3">
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusBadge(file.status)}`}
        >
          {file.status}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-zinc-600">{file.segment_count}</td>
      <td className="px-4 py-3 text-sm text-zinc-600">{formatDurationSeconds(file.duration_seconds)}</td>
      <td className="px-4 py-3 text-sm text-zinc-500">{formatDateTime(file.uploaded_at)}</td>
      <td className="px-4 py-3 text-right">
        <button
          type="button"
          onClick={() => onDelete(file)}
          disabled={deleting}
          className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-50"
          title={`Delete ${file.filename}`}
        >
          <IconTrash className="h-3.5 w-3.5" />
          {deleting ? "Deleting…" : "Delete"}
        </button>
      </td>
    </tr>
  );
}

function LibraryFileCard({ file, deleting, onPreview, onDelete }: LibraryItemProps) {
  return (
    <article className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex gap-3">
        <FileThumbnail file={file} onClick={() => onPreview(file)} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-900">{file.filename}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="text-xs capitalize text-zinc-500">{file.modality}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusBadge(file.status)}`}
            >
              {file.status}
            </span>
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
        <span>
          {file.segment_count} segments · {formatDurationSeconds(file.duration_seconds)}
        </span>
        <span>{formatDateTime(file.uploaded_at)}</span>
      </div>
      <button
        type="button"
        onClick={() => onDelete(file)}
        disabled={deleting}
        className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-full border border-rose-200 px-3 py-2 text-xs font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-50"
        title={`Delete ${file.filename}`}
      >
        <IconTrash className="h-3.5 w-3.5" />
        {deleting ? "Deleting…" : "Delete"}
      </button>
    </article>
  );
}

export function LibraryView() {
  const { state, refreshLibrary, deleteLibraryFile } = useApp();
  const { library } = state;
  const [previewFile, setPreviewFile] = useState<LibraryFileItem | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function handleDelete(file: LibraryFileItem) {
    const confirmed = window.confirm(
      `Delete "${file.filename}"? This removes the file from Cloudinary, Qdrant, and Neon.`,
    );
    if (!confirmed) {
      return;
    }

    setDeletingId(file.id);
    try {
      await deleteLibraryFile(file.id);
      if (previewFile?.id === file.id) {
        setPreviewFile(null);
      }
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 sm:text-2xl">My Index</h1>
            <p className="mt-1.5 text-sm text-zinc-500 sm:mt-2">
              All uploaded files and their indexing status. Tap a thumbnail to preview.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refreshLibrary()}
            disabled={library.loading}
            className="w-full rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50 sm:w-auto"
          >
            {library.loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {library.error && (
          <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {library.error}
          </div>
        )}

        <div className="mt-6 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm sm:mt-8">
          {library.loading && library.files.length === 0 ? (
            <div className="flex items-center justify-center px-6 py-16 text-sm text-zinc-500">
              Loading index…
            </div>
          ) : library.files.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">
              No files indexed yet. Upload text, audio, or video to get started.
            </div>
          ) : (
            <>
              <div className="space-y-3 p-3 md:hidden">
                {library.files.map((file) => (
                  <LibraryFileCard
                    key={file.id}
                    file={file}
                    deleting={deletingId === file.id}
                    onPreview={setPreviewFile}
                    onDelete={(item) => void handleDelete(item)}
                  />
                ))}
              </div>
              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-full">
                  <thead className="bg-zinc-50 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                    <tr>
                      <th className="px-4 py-3">Preview</th>
                      <th className="px-4 py-3">File</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Segments</th>
                      <th className="px-4 py-3">Duration</th>
                      <th className="px-4 py-3">Uploaded</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {library.files.map((file) => (
                      <LibraryRow
                        key={file.id}
                        file={file}
                        deleting={deletingId === file.id}
                        onPreview={setPreviewFile}
                        onDelete={(item) => void handleDelete(item)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>

      {previewFile && (
        <MediaPreviewModal file={previewFile} onClose={() => setPreviewFile(null)} />
      )}
    </div>
  );
}
