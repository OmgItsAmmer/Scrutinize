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
};

export function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled,
  loading,
  showNewSession = false,
}: ChatInputProps) {
  const { state: { search }, setWebSearchMode, clearSearch } = useApp();
  const [webSearchOpen, setWebSearchOpen] = useState(false);
  const webSearchRef = useRef<HTMLDivElement>(null);
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
          className="absolute -top-10 left-0 z-20 flex items-center gap-1.5 rounded-lg border border-white/40 bg-white/40 backdrop-blur-lg px-2.5 py-1 text-xs font-medium text-zinc-700 shadow-sm transition hover:bg-white/60 active:scale-95 cursor-pointer sm:-top-11"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          New Session
        </button>
      )}

      <div
        className="relative w-full rounded-2xl border border-white/60 bg-white/20 backdrop-blur-3xl saturate-150 transition-all duration-300 focus-within:border-zinc-400/80 focus-within:bg-white/35 focus-within:shadow-[0_12px_40px_rgba(0,0,0,0.06)]"
        style={{ boxShadow: "var(--chatly-input-shadow)" }}
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
              <ModelSelector disabled={disabled || loading} />
              <div ref={webSearchRef} className="relative">
                <button
                  type="button"
                  onClick={() => setWebSearchOpen((prev) => !prev)}
                  disabled={disabled || loading}
                  className="flex items-center gap-1 rounded-lg border border-white/60 bg-white/20 backdrop-blur-md px-2 py-1 text-[11px] font-medium text-zinc-700 transition hover:bg-white/40 disabled:cursor-not-allowed disabled:opacity-50 sm:gap-1.5 sm:px-2.5 sm:text-xs cursor-pointer"
                  title="Search web mode selection"
                >
                  <IconGlobe className="h-3.5 w-3.5 shrink-0 text-zinc-700" />
                  <span>
                    Web Search: {search.webSearchMode === "auto" ? "Auto" : search.webSearchMode === "always" ? "Always" : "Never"}
                  </span>
                </button>

                {webSearchOpen && (
                  <ul
                    role="listbox"
                    className="absolute bottom-full left-0 z-20 mb-1.5 min-w-[140px] overflow-hidden rounded-xl border border-white/60 bg-white/30 backdrop-blur-2xl saturate-150 py-1 shadow-lg"
                  >
                    {(["auto", "always", "never"] as const).map((mode) => (
                      <li key={mode}>
                        <button
                          type="button"
                          onClick={() => {
                            setWebSearchMode(mode);
                            setWebSearchOpen(false);
                          }}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition hover:bg-[var(--chatly-dropdown-hover)] text-zinc-800 hover:text-zinc-950 font-medium"
                        >
                          <div className="w-3.5 h-3.5 flex items-center justify-center shrink-0">
                            {search.webSearchMode === mode && (
                              <IconCheck className="h-3.5 w-3.5 text-zinc-950" />
                            )}
                          </div>
                          <span className="capitalize">{mode}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
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

