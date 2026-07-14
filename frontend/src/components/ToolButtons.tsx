import React from "react";
import { CHAT_TOOLS, type ChatToolId } from "../lib/chatTools";

const TOOL_ICONS: Record<ChatToolId, React.ReactNode> = {
  draft_document: (
    <svg className="h-4.5 w-4.5 shrink-0 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  ),
  flowchart: (
    <svg className="h-4.5 w-4.5 shrink-0 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  ),
  slides: (
    <svg className="h-4.5 w-4.5 shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  ),
};

interface ToolButtonsProps {
  selectedTool: ChatToolId | null;
  onSelect: (toolId: ChatToolId) => void;
  disabled?: boolean;
}

export function ToolButtons({ selectedTool, onSelect, disabled = false }: ToolButtonsProps) {
  return (
    <div className="mt-4 flex w-full flex-wrap items-center justify-center gap-3">
      {CHAT_TOOLS.map((tool) => {
        const isSelected = selectedTool === tool.id;
        return (
          <button
            key={tool.id}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(tool.id)}
            aria-pressed={isSelected}
            className={[
              "glass-panel pointer-events-auto flex cursor-pointer items-center gap-2.5 rounded-full px-4.5 py-2 text-xs font-semibold transition-all duration-200",
              "bg-white/60 text-[var(--app-text)] dark:bg-black/35",
              disabled ? "cursor-not-allowed opacity-50" : "hover:-translate-y-0.5 hover:shadow-md active:translate-y-0",
              isSelected
                ? "ring-2 ring-blue-400/70 shadow-[0_8px_24px_rgba(59,130,246,0.22)] outline outline-2 outline-blue-300/50 -translate-y-0.5"
                : "ring-1 ring-transparent",
            ].join(" ")}
          >
            {TOOL_ICONS[tool.id]}
            <span>{tool.label}</span>
          </button>
        );
      })}
    </div>
  );
}
