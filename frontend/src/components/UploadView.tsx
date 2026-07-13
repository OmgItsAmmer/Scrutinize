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
      return "bg-[var(--app-bg-glass-strong)] text-[var(--app-text-soft)]";
    case "running":
      return "bg-[var(--app-info-bg)] text-[var(--app-info)]";
    case "done":
      return "bg-[var(--app-success-bg)] text-[var(--app-success)]";
    case "failed":
      return "bg-[var(--app-danger-bg)] text-[var(--app-danger)]";
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
        <h1 className="text-xl font-semibold text-[var(--app-text)] sm:text-2xl">Upload content</h1>
        <p className="mt-2 text-sm text-[var(--app-text-muted)]">
          Add text, PDF, audio, or video files. Scrutinize will index them in the background.
        </p>

        {!apiConnected && (
          <div className="mt-6 rounded-2xl border border-[var(--app-border)] bg-[var(--app-warning-bg)] px-4 py-3 text-sm text-[var(--app-warning)] backdrop-blur-xl">
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
              ? "border-[var(--app-primary)] bg-[var(--app-bg-glass-strong)] backdrop-blur-md"
              : "border-[var(--app-border)] bg-[var(--app-bg-glass)] backdrop-blur-2xl saturate-150 hover:bg-[var(--app-bg-glass-strong)]"
          } ${!apiConnected ? "pointer-events-none opacity-50" : ""}`}
        >
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] text-[var(--app-text-soft)]">
            <IconUpload className="h-6 w-6" />
          </div>
          <p className="text-base font-medium text-[var(--app-text)]">Drag and drop files here</p>
          <p className="mt-2 text-sm text-[var(--app-text-muted)]">
            .txt, .md, .pdf, .mp3, .wav, .m4a, .mp4, .mov
          </p>
          <button
            type="button"
            disabled={!apiConnected || upload.uploading}
            onClick={() => inputRef.current?.click()}
            className="app-primary-button mt-6 rounded-full px-5 py-2.5 text-sm font-medium transition disabled:opacity-50"
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
          <div className="mt-4 rounded-2xl border border-[var(--app-border)] bg-[var(--app-danger-bg)] px-4 py-3 text-sm text-[var(--app-danger)] backdrop-blur-xl">
            {upload.error}
          </div>
        )}

        {upload.activeJobs.length > 0 && (
          <div className="mt-8 space-y-3">
            <h2 className="text-sm font-semibold text-[var(--app-text)]">Processing queue</h2>
            {upload.activeJobs.map((job) => (
              <div
                key={job.jobId}
                className="flex items-start justify-between gap-4 rounded-2xl border border-[var(--app-border)] bg-[var(--app-bg-glass)] p-4 shadow-sm backdrop-blur-xl saturate-150"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-[var(--app-text)]">{job.filename}</p>
                  <p className="mt-1 text-xs capitalize text-[var(--app-text-muted)]">{job.modality}</p>
                  {job.errorMessage && (
                    <p className="mt-2 text-xs text-[var(--app-danger)]">{job.errorMessage}</p>
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
                      className="text-xs text-[var(--app-text-muted)] hover:text-[var(--app-text)]"
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
