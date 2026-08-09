import { useEffect, useRef } from "react";
import { AnimatedPlaceholder } from "./AnimatedPlaceholder";
import { IconSend, IconGlobe } from "./icons";
import { ModelSelector } from "./ModelSelector";
import { useApp } from "../context/AppContext";

type ChatInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  loading?: boolean;
  showNewSession?: boolean;
  webOnly?: boolean;
  onAttach?: (file: File) => void;
  attachments?: { file_id: string; filename: string; status: string }[];
  attachDisabled?: boolean;
};

export function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled,
  loading,
  showNewSession = false,
  webOnly = false,
  onAttach,
  attachDisabled,
}: ChatInputProps) {
  const { clearSearch } = useApp();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const showAnimatedPlaceholder = !value && !disabled;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow height of textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    // Clamp between 44px (min) and 200px (max)
    const nextHeight = Math.max(44, Math.min(textarea.scrollHeight, 200));
    textarea.style.height = `${nextHeight}px`;
  }, [value]);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <div className="relative w-full">
      {showNewSession && (
        <button
          type="button"
          onClick={clearSearch}
          className="absolute -top-10 left-0 z-20 flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] px-2.5 py-1 text-xs font-medium text-[var(--app-text-soft)] shadow-sm backdrop-blur-lg transition hover:bg-white/70 active:scale-95 sm:-top-11"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          New Session
        </button>
      )}

      <div
        className="relative w-full rounded-2xl border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] backdrop-blur-xl transition-all duration-300 shadow-[0_0_20px_rgba(0,0,0,0.06),_0_0_40px_rgba(0,0,0,0.03)] hover:shadow-[0_0_25px_rgba(0,0,0,0.12),_0_0_50px_rgba(0,0,0,0.06)] hover:-translate-y-1 focus-within:bg-[var(--app-bg-elevated)] focus-within:shadow-[0_0_35px_rgba(0,0,0,0.18),_0_0_70px_rgba(0,0,0,0.09)] focus-within:-translate-y-1"
      >
        <form onSubmit={handleSubmit} className="flex flex-col gap-2 p-3 sm:px-4 sm:py-3.5">
          <div className="relative min-h-[44px] min-w-0 w-full">
            {showAnimatedPlaceholder && <AnimatedPlaceholder paused={Boolean(value)} />}
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(event) => onChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  onSubmit();
                }
              }}
              disabled={disabled || loading}
              className="relative z-10 block w-full resize-none bg-transparent py-1.5 text-[14px] leading-relaxed text-[var(--chatly-text-primary)] outline-none disabled:opacity-50 sm:text-[15px] overflow-y-auto"
              aria-label="Search query"
              style={{ height: "44px" }}
            />
          </div>
          
          <div className="flex items-center justify-between pt-2 border-t border-[var(--chatly-border)]/40 mt-1">
            <div className="flex items-center gap-2">
              {onAttach && (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    accept=".pdf,.txt,.md,.doc,.docx,.csv,.json"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) onAttach(file);
                      event.target.value = "";
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={disabled || loading || attachDisabled}
                    className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass)] text-[var(--app-text-soft)] transition hover:bg-[var(--app-bg-glass-strong)] disabled:cursor-not-allowed disabled:opacity-50"
                    title="Attach document"
                    aria-label="Attach document"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                </>
              )}
              <ModelSelector disabled={disabled || loading} />
              {webOnly && (
                <span className="flex items-center gap-1.5 rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] px-2.5 py-1 text-xs font-medium text-[var(--app-text-soft)]">
                  <IconGlobe className="h-3.5 w-3.5" /> Web only
                </span>
              )}
            </div>
            <button
              type="submit"
              disabled={disabled || loading || !value.trim()}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--chatly-send-bg)] text-white transition hover:bg-[var(--chatly-send-hover)] disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Search"
            >
              <IconSend className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

