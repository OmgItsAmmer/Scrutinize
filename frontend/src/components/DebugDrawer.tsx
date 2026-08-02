import { useEffect, useState } from "react";
import { fetchPipelineTraceForMessage, fetchRetrievalCandidates, fetchConversationMessages } from "../api/client";
import type {
  PipelineStepDto,
  PipelineTraceDto,
  RetrievalCandidateMatch,
} from "../types/api";
import { IconChevronDown, IconX, IconCopy } from "./icons";

const STEP_LABELS: Record<string, string> = {
  precheck: "Retrieval Pre-Check",
  rewrite: "Query Rewrite",
  gate: "Route Gate",
  retrieval: "Retrieval",
  synthesis: "Synthesis",
  evaluation: "Evaluation",
  assess_evidence: "Evidence Assessment",
  verify_citations: "Citation Verification",
  evaluate_groundedness: "Groundedness Check",
};

function stepLabel(stepType: string): string {
  return STEP_LABELS[stepType] ?? stepType;
}

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatCost(cost: number | null): string {
  if (cost === null || cost === undefined) return "—";
  return `$${cost.toFixed(6)}`;
}

function formatPct(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "success" | "danger" | "info" }) {
  const toneClass = {
    neutral: "bg-[var(--app-bg-glass-strong)] text-[var(--app-text-soft)] border-[var(--app-border)]",
    success: "bg-[var(--app-success-bg)] text-[var(--app-success)] border-transparent",
    danger: "bg-[var(--app-danger-bg)] text-[var(--app-danger)] border-transparent",
    info: "bg-[var(--app-info-bg)] text-[var(--app-info)] border-transparent",
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${toneClass}`}>
      {children}
    </span>
  );
}

function Collapsible({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass)] overflow-hidden transition-all duration-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs font-semibold text-[var(--app-text-soft)] hover:text-[var(--app-text)] hover:bg-white/5"
      >
        <span>{title}</span>
        <IconChevronDown className={`h-3.5 w-3.5 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="px-3 py-2.5 border-t border-[var(--app-border)]">{children}</div>}
    </div>
  );
}

function PrettyPrintValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined) {
    return <span className="text-[var(--app-text-muted)] italic text-[11px]">None</span>;
  }

  if (typeof value === "boolean") {
    return (
      <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${value ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"}`}>
        {value ? "TRUE" : "FALSE"}
      </span>
    );
  }

  if (typeof value === "number") {
    return <span className="font-mono text-amber-600 dark:text-amber-400 font-semibold text-[11px]">{value}</span>;
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
      try {
        const parsed = JSON.parse(trimmed);
        return <PrettyPrintValue value={parsed} depth={depth} />;
      } catch {
        // Fall back to normal string render
      }
    }
    return <p className="whitespace-pre-wrap break-words text-[var(--app-text)] text-[12px] leading-relaxed font-sans">{value}</p>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[var(--app-text-muted)] italic text-[11px]">Empty list</span>;
    return (
      <ul className="list-disc pl-4 space-y-1.5 mt-1.5">
        {value.map((item, idx) => (
          <li key={idx} className="text-[12px] text-[var(--app-text-soft)]">
            <PrettyPrintValue value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) return <span className="text-[var(--app-text-muted)] italic text-[11px]">Empty object</span>;
    return (
      <div className="grid grid-cols-1 gap-2.5 mt-1.5 w-full">
        {entries.map(([key, val]) => {
          const formattedKey = key
            .split(/[_-]/)
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(" ");

          return (
            <div key={key} className="rounded-lg border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] p-2.5 shadow-sm">
              <div className="text-[10px] font-bold text-[var(--app-text-soft)] uppercase tracking-wider mb-1.5 border-b border-[var(--app-border)] pb-1">{formattedKey}</div>
              <div className="text-[12px]">
                <PrettyPrintValue value={val} depth={depth + 1} />
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return <span className="text-[var(--app-text)] text-[11px]">{String(value)}</span>;
}

function JsonBlock({ value }: { value: unknown }) {
  const [showRaw, setShowRaw] = useState(false);

  if (value === null || value === undefined) {
    return <p className="text-xs text-[var(--app-text-muted)] italic">None</p>;
  }

  const isSimpleString = typeof value === "string" && !value.trim().startsWith("{") && !value.trim().startsWith("[");

  return (
    <div className="space-y-2">
      {!isSimpleString && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setShowRaw((r) => !r)}
            className="rounded border border-[var(--app-border)] bg-[var(--app-bg-glass)] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-[var(--app-text-soft)] hover:text-[var(--app-text)] transition-colors"
          >
            {showRaw ? "Show Pretty" : "Show Raw JSON"}
          </button>
        </div>
      )}
      {showRaw ? (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-black/5 p-2 text-[11px] leading-relaxed text-[var(--app-text)] dark:bg-white/5 font-mono">
          {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <div className="rounded-md">
          <PrettyPrintValue value={value} />
        </div>
      )}
    </div>
  );
}

const MATCH_OPTIONS: { value: RetrievalCandidateMatch; label: string }[] = [
  { value: "all", label: "All" },
  { value: "semantic", label: "Semantic only" },
  { value: "keyword", label: "Keyword only" },
  { value: "both", label: "Both lists" },
];

function RetrievalCandidatesPanel({
  runId,
  conversationId,
  attempt,
  preloadedCandidates,
  onLoaded,
}: {
  runId: string;
  conversationId: string;
  attempt: number;
  preloadedCandidates?: Array<Record<string, unknown>>;
  onLoaded?: (candidates: Array<Record<string, unknown>>) => void;
}) {
  const [match, setMatch] = useState<RetrievalCandidateMatch>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Array<Record<string, unknown>> | null>(preloadedCandidates ?? null);
  const [meta, setMeta] = useState<{ total: number; matched: number } | null>(
    preloadedCandidates ? { total: preloadedCandidates.length, matched: preloadedCandidates.length } : null
  );

  useEffect(() => {
    if (preloadedCandidates && !candidates) {
      setCandidates(preloadedCandidates);
      setMeta({ total: preloadedCandidates.length, matched: preloadedCandidates.length });
    }
  }, [preloadedCandidates, candidates]);

  function load(nextMatch: RetrievalCandidateMatch) {
    setLoading(true);
    setError(null);
    fetchRetrievalCandidates(runId, conversationId, { attempt, match: nextMatch, limit: 50 })
      .then((res) => {
        setCandidates(res.candidates);
        setMeta({ total: res.total_candidates, matched: res.matched_count });
        if (nextMatch === "all" && onLoaded) {
          onLoaded(res.candidates);
        }
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Failed to load candidates"))
      .finally(() => setLoading(false));
  }

  if (candidates === null && !loading && !error) {
    return (
      <button
        type="button"
        onClick={() => load(match)}
        className="w-full rounded-md border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] px-3 py-1.5 text-xs font-medium text-[var(--app-text)] hover:bg-[var(--app-bg-glass)]"
      >
        Show top 50 candidates
      </button>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {MATCH_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => {
              setMatch(option.value);
              load(option.value);
            }}
            className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
              match === option.value
                ? "border-[var(--app-primary)] bg-[var(--app-primary)]/10 text-[var(--app-primary)]"
                : "border-[var(--app-border)] text-[var(--app-text-soft)] hover:text-[var(--app-text)]"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      {loading && <p className="text-xs text-[var(--app-text-muted)]">Loading candidates…</p>}
      {error && <p className="text-xs text-[var(--app-danger)]">{error}</p>}
      {meta && !loading && (
        <p className="text-[11px] text-[var(--app-text-muted)]">
          Showing {meta.matched} of {meta.total} candidates
        </p>
      )}
      {candidates && !loading && (
        <div className="max-h-80 space-y-1.5 overflow-y-auto">
          {candidates.map((candidate, index) => (
            <div key={String(candidate.segment_id ?? index)} className="rounded-md border border-[var(--app-border)] bg-[var(--app-bg-glass)] px-2.5 py-1.5 text-[11px]">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium text-[var(--app-text)]">#{Number(candidate.rank ?? index + 1)}</span>
                <span className="truncate text-[var(--app-text-soft)]">{String(candidate.title ?? "Untitled")}</span>
                {candidate.in_semantic_list ? <Badge tone="info">sem #{String(candidate.semantic_rank ?? "-")}</Badge> : null}
                {candidate.in_keyword_list ? <Badge tone="success">kw #{String(candidate.keyword_rank ?? "-")}</Badge> : null}
                <span className="ml-auto text-[var(--app-text-muted)]">score {Number(candidate.score ?? 0).toFixed(4)}</span>
              </div>
              {candidate.content ? (
                <p className="mt-1 line-clamp-2 text-[var(--app-text-muted)]">{String(candidate.content)}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RetrievedSourcesList({ sources }: { sources: Array<Record<string, unknown>> }) {
  return (
    <div className="space-y-1.5">
      {sources.map((source, index) => (
        <div key={String(source.segment_id ?? index)} className="rounded-md border border-[var(--app-border)] bg-[var(--app-bg-glass)] px-2.5 py-1.5 text-[11px]">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium text-[var(--app-text)]">#{Number(source.rank ?? index + 1)}</span>
            <span className="truncate text-[var(--app-text-soft)]">{String(source.title ?? "Untitled")}</span>
            {source.in_semantic_list ? <Badge tone="info">sem #{String(source.semantic_rank ?? "-")}</Badge> : null}
            {source.in_keyword_list ? <Badge tone="success">kw #{String(source.keyword_rank ?? "-")}</Badge> : null}
            {source.rerank_score !== undefined && source.rerank_score !== null ? (
              <Badge tone="neutral">rerank {Number(source.rerank_score).toFixed(3)}</Badge>
            ) : null}
            <span className="ml-auto text-[var(--app-text-muted)]">score {Number(source.score ?? 0).toFixed(4)}</span>
          </div>
          {source.content ? (
            <p className="mt-1 line-clamp-3 text-[var(--app-text-muted)]">{String(source.content)}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function StepCard({
  step,
  runId,
  conversationId,
  preloadedCandidates,
  onCandidatesLoaded,
}: {
  step: PipelineStepDto;
  runId: string;
  conversationId: string;
  preloadedCandidates?: Array<Record<string, unknown>>;
  onCandidatesLoaded?: (candidates: Array<Record<string, unknown>>) => void;
}) {
  const statusTone = step.status === "failure" ? "danger" : "success";
  const input = step.model_input as { system?: string; user?: string } | null;

  return (
    <div className="rounded-xl border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-[var(--app-text)]">{stepLabel(step.step_type)}</span>
          <Badge>attempt {step.attempt}</Badge>
          {step.status && <Badge tone={statusTone}>{step.status}</Badge>}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--app-text-muted)]">
          {step.model_name && <span>{step.model_name}</span>}
          <span>{formatMs(step.latency_ms)}</span>
          <span>{formatCost(step.cost_usd)}</span>
        </div>
      </div>

      {(step.prompt_tokens || step.completion_tokens || step.cached_tokens) && (
        <div className="mt-1.5 flex flex-wrap gap-3 text-[11px] text-[var(--app-text-muted)]">
          {step.prompt_tokens !== null && <span>in: {step.prompt_tokens}</span>}
          {step.completion_tokens !== null && <span>out: {step.completion_tokens}</span>}
          {step.cached_tokens ? <span>cached: {step.cached_tokens}</span> : null}
        </div>
      )}

      <div className="mt-2.5 space-y-1.5">
        {step.structured_output && (
          <Collapsible title="Structured output" defaultOpen>
            <JsonBlock value={step.structured_output} />
          </Collapsible>
        )}

        {step.step_type === "retrieval" && step.retrieved_sources && step.retrieved_sources.length > 0 && (
          <Collapsible title={`Retrieved chunks (${step.retrieved_sources.length})`} defaultOpen>
            <RetrievedSourcesList sources={step.retrieved_sources} />
            {step.has_candidates && (
              <div className="mt-2 border-t border-[var(--app-border)] pt-2">
                <RetrievalCandidatesPanel
                  runId={runId}
                  conversationId={conversationId}
                  attempt={step.attempt}
                  preloadedCandidates={preloadedCandidates}
                  onLoaded={onCandidatesLoaded}
                />
              </div>
            )}
          </Collapsible>
        )}

        {input && (input.system || input.user) && (
          <Collapsible title="Prompt (system / user)">
            {input.system && (
              <div className="mb-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--app-text-muted)]">System</p>
                <JsonBlock value={input.system} />
              </div>
            )}
            {input.user && (
              <div>
                <p className="mb-1 mt-2 text-[10px] font-semibold uppercase tracking-wide text-[var(--app-text-muted)]">User</p>
                <JsonBlock value={input.user} />
              </div>
            )}
          </Collapsible>
        )}

        {step.raw_thinking && (
          <Collapsible title="Raw thinking / reasoning">
            <JsonBlock value={step.raw_thinking} />
          </Collapsible>
        )}

        {step.model_output && (
          <Collapsible title="Raw model output">
            <JsonBlock value={step.model_output} />
          </Collapsible>
        )}
      </div>
    </div>
  );
}

export function DebugDrawer({
  messageId,
  conversationId,
  onClose,
}: {
  messageId: string | null;
  conversationId: string;
  onClose: () => void;
}) {
  const open = messageId !== null;
  const [trace, setTrace] = useState<PipelineTraceDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedConv, setCopiedConv] = useState(false);
  const [copyingConversation, setCopyingConversation] = useState(false);
  const [candidatesMap, setCandidatesMap] = useState<Record<string, Array<Record<string, unknown>>>>({});

  useEffect(() => {
    if (!messageId) {
      setTrace(null);
      setError(null);
      setCandidatesMap({});
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCandidatesMap({});
    fetchPipelineTraceForMessage(messageId)
      .then(async (result) => {
        if (cancelled) return;
        setTrace(result);

        // Prefetch candidates for any retrieval step
        const retrievalSteps = result.steps.filter((s) => s.step_type === "retrieval" && s.has_candidates);
        for (const step of retrievalSteps) {
          try {
            const res = await fetchRetrievalCandidates(result.id, conversationId, {
              attempt: step.attempt,
              match: "all",
              limit: 50,
            });
            if (!cancelled) {
              setCandidatesMap((prev) => ({
                ...prev,
                [step.id]: res.candidates,
              }));
            }
          } catch (err) {
            console.error("Failed to prefetch retrieval candidates", err);
          }
        }
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Failed to load pipeline trace");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [messageId, conversationId]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && open) onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  const handleCopy = () => {
    if (!trace) return;

    // Clone trace and inject preloaded retrieval candidates
    const traceCopy = {
      ...trace,
      steps: trace.steps.map((step) => {
        if (step.step_type === "retrieval" && candidatesMap[step.id]) {
          return {
            ...step,
            retrieval_candidates: candidatesMap[step.id],
          };
        }
        return step;
      }),
    };

    navigator.clipboard.writeText(JSON.stringify(traceCopy, null, 2))
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
  };

  const handleCopyConversation = async () => {
    if (!conversationId) return;
    setCopyingConversation(true);
    try {
      const msgs = await fetchConversationMessages(conversationId);
      const enrichedMessages = await Promise.all(
        msgs.map(async (msg) => {
          const msgObj: Record<string, unknown> = {
            role: msg.role,
            content: msg.content,
            created_at: msg.created_at,
          };

          if (msg.role === "assistant" && msg.pipeline_run_id) {
            try {
              const traceData = await fetchPipelineTraceForMessage(msg.id);
              const enrichedSteps = await Promise.all(
                traceData.steps.map(async (step) => {
                  if (step.step_type === "retrieval" && step.has_candidates) {
                    try {
                      const res = await fetchRetrievalCandidates(traceData.id, conversationId, {
                        attempt: step.attempt,
                        match: "all",
                        limit: 5,
                      });
                      return {
                        ...step,
                        retrieval_candidates: res.candidates,
                      };
                    } catch (candErr) {
                      console.error("Failed to fetch candidates for copy conversation", candErr);
                      return step;
                    }
                  }
                  return step;
                })
              );

              msgObj.pipeline_stats = {
                ...traceData,
                steps: enrichedSteps,
              };
            } catch (traceErr) {
              console.error("Failed to fetch trace for copy conversation", traceErr);
            }
          }
          return msgObj;
        })
      );

      await navigator.clipboard.writeText(JSON.stringify(enrichedMessages, null, 2));
      setCopiedConv(true);
      setTimeout(() => setCopiedConv(false), 2000);
    } catch (err) {
      console.error("Failed to copy conversation stats", err);
    } finally {
      setCopyingConversation(false);
    }
  };

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-zinc-950/20 backdrop-blur-sm transition-opacity duration-300 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-[35rem] flex-col border-l border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] shadow-[0_24px_80px_rgba(15,23,42,0.18)] backdrop-blur-2xl saturate-150 transition-all duration-300 ease-out sm:max-w-[45rem] lg:max-w-[55rem] ${
          open ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-full opacity-0"
        }`}
        aria-hidden={!open}
      >
        <div className="shrink-0 border-b border-[var(--app-border)] px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--app-text-muted)]">
                Pipeline Debug
              </p>
              <h2 className="mt-0.5 truncate text-sm font-semibold text-[var(--app-text)]">
                {trace ? trace.original_query : "Loading trace…"}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                disabled={!trace}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--app-border)] bg-[var(--app-bg-glass)] px-2.5 text-xs font-medium text-[var(--app-text-soft)] hover:text-[var(--app-text)] disabled:opacity-50 transition-colors"
                title="Copy entire debug trace to clipboard"
              >
                <IconCopy className="h-3.5 w-3.5" />
                <span>{copied ? "Copied" : "Copy Query"}</span>
              </button>
              <button
                type="button"
                onClick={handleCopyConversation}
                disabled={copyingConversation}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--app-border)] bg-[var(--app-bg-glass)] px-2.5 text-xs font-medium text-[var(--app-text-soft)] hover:text-[var(--app-text)] disabled:opacity-50 transition-colors"
                title="Copy entire conversation history along with its stats (retrieved chunks limited to top 5)"
              >
                <IconCopy className="h-3.5 w-3.5" />
                <span>{copiedConv ? "Copied Chat" : copyingConversation ? "Copying…" : "Copy Chat"}</span>
              </button>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[var(--app-border)] bg-[var(--app-bg-glass)] text-[var(--app-text-soft)] hover:text-[var(--app-text)]"
                aria-label="Close debug panel"
              >
                <IconX className="h-4 w-4" />
              </button>
            </div>
          </div>

          {trace && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {trace.final_route && <Badge tone="info">route: {trace.final_route}</Badge>}
              <Badge>confidence {formatPct(trace.final_confidence)}</Badge>
              <Badge>{trace.attempts_count} attempt(s)</Badge>
              {trace.total_cost_usd !== null && <Badge tone="success">{formatCost(trace.total_cost_usd)}</Badge>}
              {trace.total_tokens !== null && <Badge>{trace.total_tokens} tokens</Badge>}
              {trace.disclaimer_appended && <Badge tone="danger">disclaimer added</Badge>}
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {loading && <p className="text-sm text-[var(--app-text-muted)]">Loading pipeline trace…</p>}
          {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          {trace && (
            <div className="space-y-2.5">
              {trace.conversation_context && trace.conversation_context.trim() && (
                <Collapsible title="Conversation Context (Previous Messages)">
                  <div className="whitespace-pre-wrap break-words rounded-md bg-black/5 p-3 text-[11px] leading-relaxed text-[var(--app-text)] dark:bg-white/5 font-mono">
                    {trace.conversation_context}
                  </div>
                </Collapsible>
              )}
              {trace.steps.map((step) => (
                <StepCard
                  key={step.id}
                  step={step}
                  runId={trace.id}
                  conversationId={conversationId}
                  preloadedCandidates={candidatesMap[step.id]}
                  onCandidatesLoaded={(cands) => {
                    setCandidatesMap((prev) => ({
                      ...prev,
                      [step.id]: cands,
                    }));
                  }}
                />
              ))}
              {trace.steps.length === 0 && (
                <p className="text-sm text-[var(--app-text-muted)]">No steps recorded for this run.</p>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

