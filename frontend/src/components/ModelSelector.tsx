import { useEffect, useRef, useState } from "react";
import { IconChevronDown, IconOpenAI } from "./icons";

export type ModelOption = {
  id: string;
  label: string;
  provider: string;
};

const MODELS: ModelOption[] = [
  { id: "gpt-4o-mini", label: "GPT-4o-mini", provider: "" },
 
];

type ModelSelectorProps = {
  disabled?: boolean;
};

export function ModelSelector({ disabled }: ModelSelectorProps) {
  const [selectedId, setSelectedId] = useState(MODELS[0].id);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = MODELS.find((model) => model.id === selectedId) ?? MODELS[0];

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1 rounded-lg border border-white/60 bg-white/20 backdrop-blur-md px-2 py-1 text-[11px] font-medium text-zinc-700 transition hover:bg-white/40 disabled:cursor-not-allowed disabled:opacity-50 sm:gap-1.5 sm:px-2.5 sm:text-xs"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <IconOpenAI className="h-3.5 w-3.5 shrink-0 text-zinc-800" />
        <span className="text-zinc-800">{selected.provider}</span>
        <span className="hidden sm:inline">{selected.label}</span>
        <span className="sm:hidden">Mini</span>
        <IconChevronDown className="h-3 w-3 opacity-60" />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute bottom-full right-0 z-20 mb-1.5 min-w-[220px] overflow-hidden rounded-xl border border-white/60 bg-white/30 backdrop-blur-2xl saturate-150 py-1 shadow-lg"
        >
          {MODELS.map((model) => (
            <li key={model.id} role="option" aria-selected={model.id === selectedId}>
              <button
                type="button"
                onClick={() => {
                  setSelectedId(model.id);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition hover:bg-[var(--chatly-dropdown-hover)] ${
                  model.id === selectedId
                    ? "font-medium text-[var(--chatly-text-primary)]"
                    : "text-[var(--chatly-text-secondary)]"
                }`}
              >
                <IconOpenAI className="h-3.5 w-3.5 shrink-0" />
                <span>
                  <span className="text-[var(--chatly-text-primary)]">{model.provider}</span>{" "}
                  {model.label}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
