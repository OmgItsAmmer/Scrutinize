import { AnimatedPlaceholder } from "./AnimatedPlaceholder";
import { IconSend } from "./icons";
import { ModelSelector } from "./ModelSelector";

type ChatInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  loading?: boolean;
};

export function ChatInput({ value, onChange, onSubmit, disabled, loading }: ChatInputProps) {
  const showAnimatedPlaceholder = !value && !disabled;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <div className="w-full rounded-[20px] border border-[var(--chatly-border)] bg-[var(--chatly-panel)] transition focus-within:border-zinc-300"
      style={{ boxShadow: "var(--chatly-input-shadow)" }}
    >
      <form onSubmit={handleSubmit} className="relative px-3 pt-3 pb-2.5 sm:px-5 sm:pt-4 sm:pb-3">
        <div className="flex items-start gap-3">
          <div className="relative min-h-[44px] min-w-0 flex-1">
            {showAnimatedPlaceholder && <AnimatedPlaceholder paused={Boolean(value)} />}
            <textarea
              value={value}
              onChange={(event) => onChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  onSubmit();
                }
              }}
              disabled={disabled || loading}
              rows={1}
              className="relative z-10 w-full resize-none bg-transparent text-[15px] leading-relaxed text-[var(--chatly-text-primary)] outline-none disabled:opacity-50"
              aria-label="Search query"
            />
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

        <div className="mt-3 flex items-center justify-end">
          <ModelSelector disabled={disabled || loading} />
        </div>
      </form>
    </div>
  );
}
