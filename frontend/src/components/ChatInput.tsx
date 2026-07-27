import { useEffect, useRef, useState } from "react";
import { AnimatedPlaceholder } from "./AnimatedPlaceholder";
import { IconSend, IconGlobe } from "./icons";
import { ModelSelector } from "./ModelSelector";
import { useApp } from "../context/AppContext";

function IconCheck(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" {...props}>
      <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

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
  const { state: { search }, setWebSearchMode, clearSearch } = useApp();
  const [webSearchOpen, setWebSearchOpen] = useState(false);
  const webSearchRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const showAnimatedPlaceholder = !value && !disabled;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (webSearchRef.current && !webSearchRef.current.contains(event.target as Node)) {
        setWebSearchOpen(false);
      }
    }
    if (webSearchOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [webSearchOpen]);

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
              {webOnly ? (
                <span className="flex items-center gap-1.5 rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] px-2.5 py-1 text-xs font-medium text-[var(--app-text-soft)]">
                  <IconGlobe className="h-3.5 w-3.5" /> Web only
                </span>
              ) : <div ref={webSearchRef} className="relative">
                <button
                  type="button"
                  onClick={() => setWebSearchOpen((prev) => !prev)}
                  disabled={disabled || loading}
                  className="flex cursor-pointer items-center gap-1 rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass)] px-2 py-1 text-[11px] font-medium text-[var(--app-text-soft)] backdrop-blur-md transition hover:bg-[var(--app-bg-glass-strong)] disabled:cursor-not-allowed disabled:opacity-50 sm:gap-1.5 sm:px-2.5 sm:text-xs"
                  title="Search web mode selection"
                >
                  <IconGlobe className="h-3.5 w-3.5 shrink-0 text-[var(--app-text-soft)]" />
                  <span>
                    Web Search: {search.webSearchMode === "auto" ? "Auto" : search.webSearchMode === "always" ? "Always" : "Never"}
                  </span>
                </button>

                {webSearchOpen && (
                  <ul
                    role="listbox"
                    className="absolute bottom-full left-0 z-20 mb-1.5 min-w-[140px] overflow-hidden rounded-xl border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] py-1 shadow-lg backdrop-blur-2xl saturate-150"
                  >
                    {(["auto", "always", "never"] as const).map((mode) => (
                      <li key={mode}>
                        <button
                          type="button"
                          onClick={() => {
                            setWebSearchMode(mode);
                            setWebSearchOpen(false);
                          }}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs font-medium text-[var(--app-text-soft)] transition hover:bg-[var(--app-dropdown-hover)] hover:text-[var(--app-text)]"
                        >
                          <div className="w-3.5 h-3.5 flex items-center justify-center shrink-0">
                            {search.webSearchMode === mode && (
                              <IconCheck className="h-3.5 w-3.5 text-[var(--app-text)]" />
                            )}
                          </div>
                          <span className="capitalize">{mode}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>}
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

