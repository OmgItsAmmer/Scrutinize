import { useApp } from "../context/AppContext";
import { formatDateTime, formatDurationSeconds } from "../lib/format";
import type { FileStatus, LibraryFileItem } from "../types/api";

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

function LibraryRow({ file }: { file: LibraryFileItem }) {
  return (
    <tr className="border-b border-zinc-100 last:border-0">
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
    </tr>
  );
}

export function LibraryView() {
  const { state, refreshLibrary } = useApp();
  const { library } = state;

  return (
    <div className="flex h-full flex-col overflow-y-auto px-8 py-8">
      <div className="mx-auto w-full max-w-5xl">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-900">My Index</h1>
            <p className="mt-2 text-sm text-zinc-500">
              All uploaded files and their indexing status.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refreshLibrary()}
            disabled={library.loading}
            className="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
          >
            {library.loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {library.error && (
          <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {library.error}
          </div>
        )}

        <div className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
          {library.loading && library.files.length === 0 ? (
            <div className="flex items-center justify-center px-6 py-16 text-sm text-zinc-500">
              Loading index…
            </div>
          ) : library.files.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">
              No files indexed yet. Upload text, audio, or video to get started.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="bg-zinc-50 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  <tr>
                    <th className="px-4 py-3">File</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Segments</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {library.files.map((file) => (
                    <LibraryRow key={file.id} file={file} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
