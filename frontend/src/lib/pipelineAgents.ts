export type AgentOutput = {
  id: string;
  agent: string;
  model: string | null;
  content: string;
  status: "active" | "complete";
  step: string;
};

const AGENT_BY_STEP: Record<string, string> = {
  gate: "Router",
  gate_end: "Router",
  escalate: "Router",
  rewrite: "Query Optimizer",
  rewrite_end: "Query Optimizer",
  retry: "Query Optimizer",
  retrieval: "Retriever",
  retrieval_end: "Retriever",
  synthesis: "Synthesizer",
  evaluation: "Verifier",
  evaluation_end: "Verifier",
  decision: "Verifier",
  web_search: "Web Search",
  web_search_end: "Web Search",
};

const STEP_STARTS = new Set([
  "gate",
  "rewrite",
  "retrieval",
  "synthesis",
  "evaluation",
  "decision",
  "escalate",
  "retry",
  "web_search",
]);

const STEP_ENDS = new Set([
  "gate_end",
  "rewrite_end",
  "retrieval_end",
  "evaluation_end",
  "web_search_end",
]);

export function agentNameFromStep(step: string): string {
  return AGENT_BY_STEP[step] ?? "Pipeline";
}

export function isStepStart(step: string): boolean {
  return STEP_STARTS.has(step);
}

export function isStepEnd(step: string): boolean {
  return STEP_ENDS.has(step);
}

type StreamStatusData = {
  step: string;
  message?: string | null;
  model?: string | null;
  route?: string;
  rewritten?: string;
  sources_count?: number;
  sources?: Array<{ title?: string }>;
  confidence?: number;
  verdict?: string;
  feedback?: string;
};

export function formatAgentOutput(step: string, data: StreamStatusData): string {
  if (step === "gate_end" && data.route) {
    return `Route: ${data.route.toUpperCase()}${data.message ? ` — ${data.message}` : ""}`;
  }
  if (step === "rewrite_end" && data.rewritten) {
    return `"${data.rewritten}"`;
  }
  if (step === "retrieval_end") {
    const count = data.sources_count ?? data.sources?.length ?? 0;
    const titles = (data.sources ?? [])
      .slice(0, 3)
      .map((source) => source.title)
      .filter(Boolean);
    const titleLine = titles.length > 0 ? `\n${titles.map((t) => `• ${t}`).join("\n")}` : "";
    return `Found ${count} relevant match${count === 1 ? "" : "es"}${titleLine}`;
  }
  if (step === "evaluation_end") {
    const parts = [data.message];
    if (data.verdict) parts.push(`Verdict: ${data.verdict}`);
    if (data.confidence != null) parts.push(`Confidence: ${Math.round(data.confidence * 100)}%`);
    return parts.filter(Boolean).join(" · ");
  }
  if (step === "web_search_end") {
    const count = data.sources_count ?? data.sources?.length ?? 0;
    return `Found ${count} web result${count === 1 ? "" : "s"}`;
  }
  return data.message?.trim() || "";
}

function findActiveIndex(outputs: AgentOutput[], agent: string): number {
  for (let i = outputs.length - 1; i >= 0; i -= 1) {
    if (outputs[i].agent === agent && outputs[i].status === "active") {
      return i;
    }
  }
  return -1;
}

export function startAgentOutput(
  outputs: AgentOutput[],
  step: string,
  model: string | null,
  message: string | null,
): AgentOutput[] {
  const agent = agentNameFromStep(step);
  const next = outputs.map((entry) =>
    entry.status === "active" ? { ...entry, status: "complete" as const } : entry,
  );

  return [
    ...next,
    {
      id: `${step}-${next.length}`,
      agent,
      model,
      content: message?.trim() || "",
      status: "active",
      step,
    },
  ];
}

export function completeAgentOutput(
  outputs: AgentOutput[],
  step: string,
  model: string | null,
  content: string,
): AgentOutput[] {
  const agent = agentNameFromStep(step);
  const activeIndex = findActiveIndex(outputs, agent);
  const trimmed = content.trim();

  if (activeIndex >= 0) {
    return outputs.map((entry, index) =>
      index === activeIndex
        ? { ...entry, model: model ?? entry.model, content: trimmed || entry.content, status: "complete", step }
        : entry,
    );
  }

  return [
    ...outputs,
    {
      id: `${step}-${outputs.length}`,
      agent,
      model,
      content: trimmed,
      status: "complete",
      step,
    },
  ];
}

export function appendSynthesizerOutput(outputs: AgentOutput[], text: string): AgentOutput[] {
  const activeIndex = findActiveIndex(outputs, "Synthesizer");
  if (activeIndex < 0) {
    return [
      ...outputs,
      {
        id: `synthesis-${outputs.length}`,
        agent: "Synthesizer",
        model: null,
        content: text,
        status: "active",
        step: "synthesis",
      },
    ];
  }

  return outputs.map((entry, index) =>
    index === activeIndex ? { ...entry, content: entry.content + text } : entry,
  );
}

export function applyStreamStatus(
  outputs: AgentOutput[],
  data: StreamStatusData,
): AgentOutput[] {
  const step = data.step;
  if (!step) return outputs;

  if (isStepEnd(step)) {
    return completeAgentOutput(
      outputs,
      step,
      data.model ?? null,
      formatAgentOutput(step, data),
    );
  }

  if (isStepStart(step)) {
    return startAgentOutput(outputs, step, data.model ?? null, data.message ?? null);
  }

  return outputs;
}
