import { useState, useEffect, useRef } from "react";
import type { AgentOutput } from "../lib/pipelineAgents";
import { IconChevronDown } from "./icons";

type ThinkingPanelProps = {
  outputs: AgentOutput[];
  loading: boolean;
};

function getAgentCatchyName(agentName: string) {
  const name = agentName.toLowerCase();
  if (name.includes("precheck") || name.includes("pre-check")) return "Pre-Check";
  if (name.includes("router") || name.includes("gate")) return "Gate";
  if (name.includes("optimizer") || name.includes("rewriter") || name.includes("rewrite")) return "Rewriter";
  if (name.includes("evidence") || name.includes("assess_evidence")) return "Assess Evidence";
  if (name.includes("synthesizer") || name.includes("synthesis") || name.includes("synthesize") || name.includes("writer")) return "Synthesis";
  if (name.includes("citation") || name.includes("verify_citations") || name.includes("verify_and_evaluate")) return "Verify Citations";
  if (name.includes("groundedness") || name.includes("evaluate_groundedness")) return "Groundedness";
  if (name.includes("verifier") || name.includes("decision") || name.includes("decide") || name.includes("evaluation")) return "Decision";
  if (name.includes("retriever") || name.includes("search") || name.includes("retrieval")) return "Retrieval";
  return agentName;
}

export function ThinkingPanel({ outputs, loading }: ThinkingPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const currentOutput = outputs.find((o) => o.status === "active") || outputs[outputs.length - 1];
  const agentName = currentOutput ? getAgentCatchyName(currentOutput.agent) : "Thinking";

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
      {hasOutputs && isExpanded && currentOutput && (
        <div
          ref={listRef}
          className="thinking-panel-body max-h-44 space-y-0 overflow-y-auto border-b border-white/20 px-3.5 py-2.5 sm:max-h-52 sm:px-4"
        >
          <div className="thinking-agent-row py-1">
            <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className="text-xs font-semibold text-zinc-700">{agentName}</span>
              {currentOutput.status === "active" && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-500" />
              )}
            </div>
            {currentOutput.content && (
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-zinc-600">
                {currentOutput.content}
                {currentOutput.status === "active" && currentOutput.agent === "Synthesizer" && (
                  <span className="ml-0.5 inline-block h-3.5 w-1 animate-pulse bg-zinc-500 align-middle" />
                )}
              </p>
            )}
          </div>
        </div>
      )}

      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="thinking-panel-header flex cursor-pointer select-none items-center justify-between gap-3 px-3.5 py-2.5 sm:px-4 hover:bg-white/10 transition-colors"
      >
        <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1.5 min-w-0">
          <div className="flex items-center gap-2 shrink-0">
            <style>{`
              @keyframes blink-bw {
                0%, 100% { background-color: #000000; }
                50% { background-color: #ffffff; border: 1px solid #000000; }
              }
              .animate-blink-bw {
                animation: blink-bw 1s infinite;
              }
            `}</style>
            <span className="animate-blink-bw h-2 w-2 shrink-0 rounded-full border border-black" />
            <span className="text-sm font-medium text-zinc-800">
              {agentName}
            </span>
          </div>
        </div>

        <IconChevronDown
          className={`h-4 w-4 text-zinc-400 transition-transform duration-200 shrink-0 ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </div>
    </div>
  );
}

