import { useState, useEffect, useRef } from "react";
import type { AgentOutput } from "../lib/pipelineAgents";
import { IconChevronDown } from "./icons";

type ThinkingPanelProps = {
  outputs: AgentOutput[];
  loading: boolean;
};

export function ThinkingPanel({ outputs, loading }: ThinkingPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [outputs]);

  // Reset to compact when loading status changes
  useEffect(() => {
    if (loading) {
      setIsExpanded(false);
    }
  }, [loading]);

  if (!loading) {
    return null;
  }

  const hasOutputs = outputs.length > 0;

  return (
    <div className="thinking-panel thinking-panel-enter mb-2 overflow-hidden rounded-2xl rounded-b-md">
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="thinking-panel-header flex cursor-pointer select-none items-center justify-between gap-3 px-3.5 py-2.5 sm:px-4 hover:bg-white/10 transition-colors"
      >
        <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1.5 min-w-0">
          <div className="flex items-center gap-2 shrink-0">
            <span className="thinking-dot h-1.5 w-1.5 shrink-0 rounded-full" />
            <span className="text-sm font-medium text-zinc-500">
              thinking
              <span className="thinking-ellipsis" aria-hidden>
                ...
              </span>
            </span>
          </div>

          {!isExpanded && hasOutputs && (
            <div className="flex flex-wrap items-center gap-1.5">
              {outputs.map((output) => {
                let agentShort = output.agent;
                if (output.agent === "Query Optimizer") agentShort = "Rewrite";
                else if (output.agent === "Router") agentShort = "Gate";
                else if (output.agent === "Retriever") agentShort = "Retrieval";
                else if (output.agent === "Synthesizer") agentShort = "Synthesis";
                else if (output.agent === "Verifier") agentShort = "Decision";

                return (
                  <div
                    key={output.id}
                    className="flex items-center gap-1 rounded bg-white/15 dark:bg-black/20 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500"
                  >
                    <span>{agentShort}</span>
                    {output.model && (
                      <span className="border-l border-zinc-400/20 pl-1 font-mono text-[9px] opacity-75">
                        {output.model}
                      </span>
                    )}
                    {output.status === "active" && (
                      <span className="ml-0.5 h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-400" />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <IconChevronDown
          className={`h-4 w-4 text-zinc-400 transition-transform duration-200 shrink-0 ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </div>

      {hasOutputs && isExpanded && (
        <div
          ref={listRef}
          className="thinking-panel-body max-h-44 space-y-0 overflow-y-auto border-t border-white/20 px-3.5 py-2 sm:max-h-52 sm:px-4"
        >
          {outputs.map((output) => (
            <div
              key={output.id}
              className={`thinking-agent-row border-b border-white/10 py-2.5 last:border-b-0 ${
                output.status === "active" ? "thinking-agent-active" : ""
              }`}
            >
              <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="text-xs font-semibold text-zinc-600">{output.agent}</span>
                {output.model && (
                  <span className="rounded-md bg-white/30 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">
                    {output.model}
                  </span>
                )}
                {output.status === "active" && (
                  <span className="h-1 w-1 animate-pulse rounded-full bg-zinc-400" />
                )}
              </div>
              {output.content && (
                <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-zinc-600">
                  {output.content}
                  {output.status === "active" && output.agent === "Synthesizer" && (
                    <span className="ml-0.5 inline-block h-3.5 w-1 animate-pulse bg-zinc-500 align-middle" />
                  )}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

