import { useRef } from "react";
import { useApp } from "../context/AppContext";
import type { JobStatus } from "../types/api";
import { IconUpload } from "./icons";

const ACCEPT =
  ".txt,.md,.pdf,.mp3,.wav,.m4a,.mp4,.mov,text/plain,text/markdown,application/pdf,audio/mpeg,audio/wav,audio/mp4,video/mp4,video/quicktime";

function statusLabel(status: JobStatus): string {
  switch (status) {
    case "pending":
      return "Queued";
    case "running":
      return "Processing";
    case "done":
      return "Indexed";
    case "failed":
      return "Failed";
  }
}

function statusClass(status: JobStatus): string {
  switch (status) {
    case "pending":
      return "bg-zinc-100 text-zinc-700";
    case "running":
      return "bg-sky-100 text-sky-800";
    case "done":
      return "bg-emerald-100 text-emerald-800";
    case "failed":
      return "bg-rose-100 text-rose-800";
  }
}

export function UploadView() {
  const { state, uploadFiles, setDragActive, dismissUploadJob } = useApp();
  const inputRef = useRef<HTMLInputElement>(null);
  const { upload, apiConnected } = state;

  function handleFiles(fileList: FileList | null) {
    if (!fileList) {
      return;
    }
    void uploadFiles(fileList);
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
      <div className="mx-auto w-full max-w-2xl">
        <h1 className="text-xl font-semibold text-zinc-900 sm:text-2xl">Upload content</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Add text, PDF, audio, or video files. Scrutinize will index them in the background.
        </p>

        {!apiConnected && (
          <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Backend is offline. Uploads are disabled until the API reconnects.
          </div>
        )}

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragActive(false);
            handleFiles(event.dataTransfer.files);
          }}
          className={`mt-6 flex flex-col items-center justify-center rounded-3xl border-2 border-dashed px-4 py-10 text-center transition sm:mt-8 sm:px-8 sm:py-16 ${
            upload.dragActive
              ? "border-zinc-900 bg-zinc-50"
              : "border-zinc-200 bg-white hover:border-zinc-300"
          } ${!apiConnected ? "pointer-events-none opacity-50" : ""}`}
        >
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-700">
            <IconUpload className="h-6 w-6" />
          </div>
          <p className="text-base font-medium text-zinc-900">Drag and drop files here</p>
          <p className="mt-2 text-sm text-zinc-500">
            .txt, .md, .pdf, .mp3, .wav, .m4a, .mp4, .mov
          </p>
          <button
            type="button"
            disabled={!apiConnected || upload.uploading}
            onClick={() => inputRef.current?.click()}
            className="mt-6 rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
          >
            {upload.uploading ? "Uploading…" : "Choose files"}
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(event) => handleFiles(event.target.files)}
          />
        </div>

        {upload.error && (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {upload.error}
          </div>
        )}

        {upload.activeJobs.length > 0 && (
          <div className="mt-8 space-y-3">
            <h2 className="text-sm font-semibold text-zinc-900">Processing queue</h2>
            {upload.activeJobs.map((job) => (
              <div
                key={job.jobId}
                className="flex items-start justify-between gap-4 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-900">{job.filename}</p>
                  <p className="mt-1 text-xs capitalize text-zinc-500">{job.modality}</p>
                  {job.errorMessage && (
                    <p className="mt-2 text-xs text-rose-600">{job.errorMessage}</p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass(job.status)}`}
                  >
                    {statusLabel(job.status)}
                  </span>
                  {(job.status === "done" || job.status === "failed") && (
                    <button
                      type="button"
                      onClick={() => dismissUploadJob(job.jobId)}
                      className="text-xs text-zinc-500 hover:text-zinc-800"
                    >
                      Dismiss
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
