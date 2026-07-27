# Scrutinize Harness Engineering — Missing Components and Implementation Plan

**Project:** Scrutinize  
**Document type:** Architecture gap analysis and implementation plan  
**Purpose:** Identify the harness-engineering capabilities that are missing or only partially implemented in the current Scrutinize architecture, and define how to add them without rebuilding the existing RAG pipeline.

---

## 1. Executive Summary

Scrutinize already contains many important harness-engineering foundations:

- `PipelineOrchestrator`
- `RetrievalPrecheck`
- `RagGate`
- RAG, web, hybrid, and generic routes
- Hybrid dense + sparse retrieval
- Project-scoped Qdrant filtering
- MCP tool integration
- Retry-based quality evaluation through `DecisionAgent`
- Pipeline observability through `pipeline_runs` and `pipeline_steps`
- Persistent V3 conversations
- Separate proposed executors for general and project chat
- Unit, integration, and system testing

The architecture is already more advanced than a standard RAG application. However, the following controls are missing or not yet explicit enough to make the system a strong, production-grade AI harness:

1. Evidence sufficiency evaluation
2. Claim-level citation verification
3. Groundedness and unsupported-claim detection
4. Prompt-injection defense for retrieved content
5. Tool permission and approval enforcement
6. Central run-budget and execution-limit control
7. Strict structured-output validation
8. Explicit abstention and failure policies
9. Adversarial agent evaluation suites
10. Trace-level decision explanations and measurable quality metrics

These additions should be implemented around the existing pipeline rather than replacing it.

---

## 2. Current Harness Capabilities

The existing query flow is:

```text
User query
    ↓
RetrievalPrecheck
    ↓
RagGate
    ↓
web_search_mode policy override
    ↓
RAG / Web / Hybrid / Generic
    ↓
RagSynthesisAgent
    ↓
DecisionAgent
    ↓
Accept or retry
    ↓
PipelineLogger
```

This already provides:

| Capability | Current component |
|---|---|
| Query routing | `RetrievalPrecheck`, `RagGate` |
| Controlled execution paths | RAG, web, hybrid, generic |
| Retrieval orchestration | `RrfRetriever`, Qdrant |
| Dense and sparse retrieval | OpenAI embeddings + BM25 |
| Project isolation | `project_id` Qdrant filters |
| Tool abstraction | `McpClientManager`, FastMCP |
| LLM abstraction | `BaseLlmClient`, local/cloud clients |
| Retry loop | `DecisionAgent`, `v2_max_pipeline_attempts` |
| Conversation context | `conversation_memory.py`, V3 persisted chat |
| Pipeline observability | `pipeline_runs`, `pipeline_steps` |
| Streaming feedback | SSE status and answer events |
| Background processing | Celery + Redis |
| Execution-policy separation | Proposed `WebOnlyChatExecutor` and `ProjectChatExecutor` |

The following sections describe what still needs to be added.

---

# 3. Missing Component 1 — Evidence Sufficiency Gate

## 3.1 Problem

The existing `RetrievalPrecheck` determines whether the query should route to RAG, web, generic, or the gate LLM. It uses retrieval scores to make routing decisions.

A high similarity score does not guarantee that the retrieved chunks contain enough information to answer the question.

Examples:

- A chunk contains the same keywords but not the requested fact.
- Multiple chunks partially answer different parts of the question.
- The retrieved source is outdated.
- Two retrieved sources conflict.
- The document contains a heading matching the query but no answer.
- The answer requires a table, image, timestamp, or attachment that was not extracted.

The system therefore needs a separate check after full retrieval and before synthesis.

## 3.2 Proposed Component

Create:

```text
backend/app/services/v2/evidence_assessor.py
```

Suggested schema:

```python
from typing import Literal
from pydantic import BaseModel, Field


class EvidenceAssessment(BaseModel):
    sufficient: bool
    confidence: float = Field(ge=0.0, le=1.0)

    supported_aspects: list[str]
    missing_aspects: list[str]

    relevant_source_ids: list[str]
    conflicting_source_ids: list[str]

    conflict_detected: bool
    outdated_source_detected: bool

    recommended_action: Literal[
        "answer",
        "retrieve_again",
        "search_web",
        "ask_clarification",
        "explain_conflict",
        "abstain",
    ]

    reason: str
```

## 3.3 Required Behavior

The evidence gate should check:

- Whether the question is answerable from the retrieved context
- Whether every important part of a multi-part question is covered
- Whether the sources are authoritative enough
- Whether sources disagree
- Whether the source is current or superseded
- Whether the result belongs to the authorized project
- Whether the answer requires information unavailable in extracted text
- Whether more retrieval or web search is necessary

## 3.4 Pipeline Placement

```text
retrieve
    ↓
rerank
    ↓
filter authorized sources
    ↓
assess evidence
    ├── sufficient → synthesize
    ├── weak → retrieve again
    ├── missing current data → web search
    ├── conflict → explain conflict
    └── insufficient → abstain
```

## 3.5 Acceptance Criteria

- The system does not answer merely because the top retrieval score is high.
- Missing evidence produces a clear abstention instead of a guessed answer.
- Multi-part questions are only answered when all required parts are supported.
- Conflicting documents are detected and reported.
- The evidence decision is recorded in `pipeline_steps`.

---

# 4. Missing Component 2 — Claim-Level Citation Verifier

## 4.1 Problem

The synthesis agent can produce citations, but the architecture does not define a deterministic verification stage that proves each citation is valid.

Possible failures:

- The model invents a source ID.
- The cited source was not included in the retrieved context.
- The citation exists but does not support the claim.
- The source belongs to another project.
- The citation points to an old or superseded policy.
- One citation is attached to a paragraph containing multiple unsupported claims.

## 4.2 Proposed Component

Create:

```text
backend/app/services/v2/citation_verifier.py
```

Suggested schemas:

```python
from pydantic import BaseModel


class AnswerClaim(BaseModel):
    claim_id: str
    text: str
    citation_ids: list[str]


class CitationCheck(BaseModel):
    claim_id: str
    source_id: str

    source_exists: bool
    source_was_retrieved: bool
    source_is_authorized: bool
    source_supports_claim: bool

    support_score: float
    reason: str


class CitationVerificationResult(BaseModel):
    valid: bool
    checks: list[CitationCheck]
    unsupported_claim_ids: list[str]
    invalid_source_ids: list[str]
```

## 4.3 Verification Rules

For every factual claim:

1. Extract or receive the claim as structured output.
2. Confirm the cited source exists.
3. Confirm the source was included in the current run.
4. Confirm the source belongs to the active project or allowed web-source set.
5. Confirm the cited text supports the claim.
6. Confirm the answer does not materially change numbers, names, dates, conditions, or exceptions.
7. Reject unsupported claims.
8. Reject citations generated from conversation memory unless explicitly allowed.

## 4.4 Recommended Citation Format

The synthesis agent should return structured claims:

```json
{
  "answer": "Employees receive 20 annual leave days.",
  "claims": [
    {
      "claim_id": "claim_1",
      "text": "Employees receive 20 annual leave days.",
      "citation_ids": ["segment_42"]
    }
  ]
}
```

The user-facing answer can still be rendered as normal text, but the verifier should operate on the structured representation.

## 4.5 Pipeline Placement

```text
synthesize
    ↓
extract claims
    ↓
verify citations
    ├── valid → groundedness evaluation
    ├── fixable → regenerate once
    └── invalid → abstain
```

## 4.6 Acceptance Criteria

- Every factual answer has at least one verified supporting source.
- Fabricated citation IDs are always rejected.
- Citations from unauthorized projects are always rejected.
- Unsupported numerical or policy claims are blocked.
- Citation-verification results appear in the pipeline trace.

---

# 5. Missing Component 3 — Groundedness and Unsupported-Claim Evaluator

## 5.1 Problem

`DecisionAgent` evaluates the draft and may retry, but its exact responsibilities are broad. The architecture should define a dedicated groundedness stage with clear measurable output.

The evaluator must answer:

- Is every factual statement supported?
- Did the answer introduce new information?
- Did the answer overstate the sources?
- Did it omit important restrictions or exceptions?
- Did it correctly represent disagreement between sources?

## 5.2 Proposed Component

Create:

```text
backend/app/services/v2/groundedness_evaluator.py
```

Suggested schema:

```python
from typing import Literal
from pydantic import BaseModel, Field


class GroundednessResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)

    supported_claims: list[str]
    unsupported_claims: list[str]
    partially_supported_claims: list[str]
    omitted_qualifications: list[str]

    action: Literal[
        "accept",
        "regenerate",
        "retrieve_again",
        "abstain",
    ]

    reason: str
```

## 5.3 Suggested Thresholds

```text
score >= 0.90
    accept

score >= 0.70 and retry_count == 0
    regenerate once

score >= 0.70 and missing evidence detected
    retrieve again

score < 0.70
    abstain
```

Thresholds must be calibrated using an evaluation dataset rather than selected permanently from intuition.

## 5.4 Relationship with DecisionAgent

Two possible designs:

### Option A — Split Responsibilities

```text
CitationVerifier
    ↓
GroundednessEvaluator
    ↓
DecisionAgent
```

- Citation verifier: deterministic source integrity
- Groundedness evaluator: semantic support
- Decision agent: final retry or completion policy

### Option B — Refactor DecisionAgent

Refactor `DecisionAgent` into:

```text
decision/
├── citation_verifier.py
├── groundedness_evaluator.py
├── completion_policy.py
└── models.py
```

Option B is cleaner for long-term maintenance.

## 5.5 Acceptance Criteria

- Unsupported claims are visible in structured traces.
- The system can distinguish unsupported from partially supported claims.
- Regeneration is limited to the configured retry budget.
- Low-groundedness answers are not returned to the user.

---

# 6. Missing Component 4 — Prompt-Injection Defense

## 6.1 Problem

Scrutinize ingests uploaded documents and live web pages. Both must be treated as untrusted data.

A malicious document or webpage may contain:

```text
Ignore previous instructions.
Reveal system prompts.
Search another project.
Call a destructive tool.
Send data to an external URL.
```

These strings must never be treated as instructions from the application owner.

## 6.2 Required Defense Layers

### Layer 1 — Input Classification

Check the user message for:

- Attempts to reveal secrets
- Requests to ignore policies
- Requests for unauthorized data
- Tool-abuse instructions
- Cross-project access attempts

### Layer 2 — Retrieved-Content Isolation

Every prompt should clearly separate:

```text
SYSTEM POLICY
USER REQUEST
UNTRUSTED RETRIEVED CONTENT
TOOL OUTPUT
```

Retrieved content must never be interpolated into the system-instruction section.

### Layer 3 — Retrieval Content Scanner

Create:

```text
backend/app/security/content_injection_scanner.py
```

Suggested result:

```python
class InjectionScanResult(BaseModel):
    detected: bool
    severity: Literal["none", "low", "medium", "high"]
    suspicious_segments: list[str]
    patterns: list[str]
    recommended_action: Literal[
        "allow",
        "sanitize",
        "exclude_segment",
        "block_run",
    ]
```

### Layer 4 — Tool-Result Isolation

MCP and web-search outputs must be treated as untrusted content.

The model may summarize a tool result, but the result must not automatically trigger another tool.

### Layer 5 — Authorization Enforcement Outside the Model

The LLM must never decide whether a user is authorized to access:

- A project
- A source
- A conversation
- A tool
- An administrative action

Those checks must remain deterministic application logic.

## 6.3 Acceptance Criteria

- Prompt injection inside a PDF does not change the pipeline's system behavior.
- Prompt injection inside a webpage does not trigger tools.
- Tool outputs cannot grant themselves permissions.
- Cross-project instructions cannot bypass project filters.
- Injection events are logged without storing sensitive full content by default.

---

# 7. Missing Component 5 — Tool Permission Registry

## 7.1 Problem

Scrutinize currently exposes MCP tools such as:

- `web_search`
- `generate_pdf`

These are relatively low risk, but future tools may include:

- Send email
- Delete source
- Modify project
- Create support ticket
- Update database record
- Publish report
- Call a third-party API

The model should be allowed to propose a tool call, but not authorize it.

## 7.2 Proposed Components

Create:

```text
backend/app/tools/policy.py
backend/app/tools/registry.py
backend/app/tools/permission_checker.py
```

Suggested schema:

```python
from typing import Literal
from pydantic import BaseModel


class ToolPolicy(BaseModel):
    name: str

    risk_level: Literal[
        "read_only",
        "low_risk_write",
        "sensitive_write",
        "destructive",
    ]

    allowed_roles: list[str]
    approval_required: bool
    maximum_calls_per_run: int

    allowed_scopes: list[str]
    timeout_seconds: int

    audit_arguments: bool = True
    redact_fields: list[str] = []
```

Example policies:

```python
TOOL_POLICIES = {
    "web_search": ToolPolicy(
        name="web_search",
        risk_level="read_only",
        allowed_roles=["member", "admin"],
        approval_required=False,
        maximum_calls_per_run=2,
        allowed_scopes=["general", "project"],
        timeout_seconds=20,
    ),
    "generate_pdf": ToolPolicy(
        name="generate_pdf",
        risk_level="low_risk_write",
        allowed_roles=["member", "admin"],
        approval_required=False,
        maximum_calls_per_run=1,
        allowed_scopes=["general", "project"],
        timeout_seconds=30,
    ),
    "delete_source": ToolPolicy(
        name="delete_source",
        risk_level="destructive",
        allowed_roles=["admin"],
        approval_required=True,
        maximum_calls_per_run=1,
        allowed_scopes=["project"],
        timeout_seconds=15,
    ),
}
```

## 7.3 Enforcement Order

```text
Model requests tool
    ↓
Validate tool exists
    ↓
Validate arguments
    ↓
Check authenticated user
    ↓
Check project membership
    ↓
Check role
    ↓
Check conversation scope
    ↓
Check run call limit
    ↓
Check approval requirement
    ↓
Execute tool
```

## 7.4 Acceptance Criteria

- Unknown tools are rejected.
- Invalid arguments are rejected before execution.
- The model cannot bypass role checks.
- A tool cannot execute more times than its configured limit.
- Sensitive arguments are redacted from logs.
- Every tool call has an audit record.

---

# 8. Missing Component 6 — Human Approval State

## 8.1 Problem

Sensitive actions require an explicit approval state. A normal chat confirmation such as "Are you sure?" is not sufficient because the LLM could misinterpret or skip it.

## 8.2 Proposed State Model

```text
requested
    ↓
policy_checked
    ↓
waiting_for_approval
    ├── rejected
    ├── expired
    └── approved
            ↓
        executing
            ↓
        completed / failed
```

Suggested table:

```sql
create table tool_approvals (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references chat_conversations(id),
  message_id uuid references chat_messages(id),
  user_id uuid not null references users(id),
  project_id uuid references projects(id),

  tool_name text not null,
  tool_arguments jsonb not null,
  risk_level text not null,

  status text not null check (
    status in (
      'waiting',
      'approved',
      'rejected',
      'expired',
      'executed',
      'failed'
    )
  ),

  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  decided_at timestamptz,
  executed_at timestamptz
);
```

## 8.3 SSE Events

Add:

```text
approval.required
approval.approved
approval.rejected
approval.expired
tool.started
tool.completed
tool.failed
```

Example:

```json
{
  "type": "approval.required",
  "data": {
    "approval_id": "uuid",
    "tool_name": "delete_source",
    "summary": "Delete source employee-policy-old.pdf",
    "risk_level": "destructive",
    "expires_at": "2026-07-26T18:00:00Z"
  }
}
```

## 8.4 Acceptance Criteria

- Sensitive tools cannot execute before approval.
- Approval is tied to exact tool arguments.
- Changing arguments invalidates the previous approval.
- Expired approvals cannot be reused.
- Approval decisions are auditable.

---

# 9. Missing Component 7 — Central Run-Budget Controller

## 9.1 Problem

The architecture currently limits pipeline attempts, but harness engineering requires centralized limits for the full run.

Without centralized budgets, an agent may:

- Repeatedly rewrite the query
- Perform too many web searches
- Call tools excessively
- Consume too many tokens
- Continue after timeouts
- Generate unexpectedly high costs

## 9.2 Proposed Component

Create:

```text
backend/app/services/v2/run_budget.py
```

Suggested schema:

```python
from pydantic import BaseModel


class RunBudget(BaseModel):
    max_pipeline_attempts: int = 2
    max_llm_calls: int = 6

    max_retrieval_calls: int = 3
    max_web_search_calls: int = 2
    max_tool_calls: int = 3

    max_input_tokens: int = 20_000
    max_output_tokens: int = 4_000

    max_duration_seconds: int = 60
    max_cost_usd: float | None = None


class RunUsage(BaseModel):
    pipeline_attempts: int = 0
    llm_calls: int = 0

    retrieval_calls: int = 0
    web_search_calls: int = 0
    tool_calls: int = 0

    input_tokens: int = 0
    output_tokens: int = 0

    estimated_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
```

## 9.3 Required Stop Reasons

Every run must end with one explicit status:

```text
completed
abstained
clarification_required
approval_required
unsafe_request
insufficient_evidence
citation_verification_failed
groundedness_failed
maximum_retries_reached
budget_exceeded
timeout
cancelled
internal_error
```

## 9.4 Integration

The orchestrator should call the budget controller:

```text
before every LLM call
before every retrieval
before every web search
before every tool call
before every retry
before synthesis
```

## 9.5 Acceptance Criteria

- No run exceeds the configured call limits.
- Timeout cancellation propagates to active tasks where possible.
- Budget usage is written to `pipeline_runs`.
- The frontend receives a clear error or completion status.
- Cost and token metrics can be aggregated per project and per user.

---

# 10. Missing Component 8 — Strict Structured-Output Validation

## 10.1 Problem

`json_utils.py` repairs or extracts JSON from raw LLM responses. This is useful as a fallback, but harness decisions should not rely on loosely parsed model output.

Critical outputs include:

- Route selection
- Tool selection
- Query rewrite
- Evidence assessment
- Citation list
- Groundedness result
- Retry decision
- Final status

## 10.2 Proposed Validation Pattern

```text
LLM output
    ↓
Strict Pydantic validation
    ├── valid → continue
    └── invalid
            ↓
        retry with validation error
            ├── valid → continue
            └── invalid again → safe fallback
```

## 10.3 Example Gate Schema

```python
from typing import Literal
from pydantic import BaseModel, Field


class GateResult(BaseModel):
    route: Literal["rag", "web", "hybrid", "generic"]
    confidence: float = Field(ge=0.0, le=1.0)
    requested_tool: str | None = None
    reason_code: Literal[
        "corpus_match",
        "current_information",
        "mixed_sources",
        "conversation",
        "explicit_tool",
        "no_corpus",
        "other",
    ]
```

## 10.4 Safe Fallbacks

| Invalid component | Safe fallback |
|---|---|
| Gate result | deterministic routing policy |
| Query rewrite | original query |
| Evidence assessment | abstain or web fallback |
| Tool call | reject tool execution |
| Citation output | do not return cited answer |
| Groundedness output | abstain |
| Decision output | stop retry loop safely |

## 10.5 Acceptance Criteria

- Invalid model output never crashes the complete request.
- Tool calls never execute from unvalidated output.
- Validation failures are visible in traces.
- Retry count is limited.
- Safe fallback behavior is covered by tests.

---

# 11. Missing Component 9 — Explicit Abstention Policy

## 11.1 Problem

The architecture should define exactly when the agent must refuse to guess.

## 11.2 Required Abstention Conditions

The system should abstain when:

- No relevant source exists.
- Evidence is insufficient.
- Sources conflict and no authority rule resolves the conflict.
- Required information is unavailable.
- Citation verification fails.
- Groundedness remains below threshold after retry.
- The answer would expose unauthorized data.
- The user requests a blocked operation.
- Run budget is exhausted before verification.
- The model repeatedly returns invalid structured output.

## 11.3 User-Facing Response Pattern

The system should return:

1. What it could not verify
2. What sources were searched
3. Why it cannot safely answer
4. What additional information would resolve the issue

Example:

```text
I could not verify the requested refund period from the available project
sources. The retrieved documents mention refund eligibility, but none specifies
the number of days. I have not guessed the value.
```

## 11.4 Acceptance Criteria

- Unsupported questions produce an abstention, not a plausible guess.
- Abstentions are distinguishable from technical failures.
- Abstention reasons are stored using stable reason codes.
- Evaluation tests measure correct abstention and unnecessary abstention separately.

---

# 12. Missing Component 10 — Adversarial Evaluation Suite

## 12.1 Problem

The existing test structure covers unit, integration, and system behavior. Agentic systems also need behavioral evaluation datasets.

Traditional tests answer:

```text
Did the function return the expected value?
```

Agent evaluations answer:

```text
Did the complete system behave safely and correctly?
```

## 12.2 Proposed Structure

```text
backend/
└── evals/
    ├── datasets/
    │   ├── routing.jsonl
    │   ├── retrieval.jsonl
    │   ├── groundedness.jsonl
    │   ├── citation_integrity.jsonl
    │   ├── prompt_injection.jsonl
    │   ├── authorization.jsonl
    │   ├── tool_permissions.jsonl
    │   ├── abstention.jsonl
    │   └── failure_recovery.jsonl
    │
    ├── graders/
    │   ├── routing_grader.py
    │   ├── retrieval_grader.py
    │   ├── citation_grader.py
    │   ├── groundedness_grader.py
    │   ├── policy_grader.py
    │   └── cost_latency_grader.py
    │
    ├── runner.py
    ├── report.py
    └── thresholds.py
```

## 12.3 Suggested Evaluation Case Schema

```json
{
  "id": "policy_001",
  "project_id": "test-project",
  "query": "How many annual leave days do employees receive?",
  "expected_behavior": "answer",
  "expected_route": "rag",
  "expected_source_ids": ["hr-policy-2026"],
  "required_facts": ["20 annual leave days"],
  "forbidden_facts": [],
  "minimum_groundedness": 0.90,
  "maximum_tool_calls": 0
}
```

## 12.4 Required Test Scenarios

### Normal RAG Behavior

1. Correct answer from one source
2. Correct answer requiring multiple chunks
3. Exact keyword query
4. Semantic query
5. Multi-turn follow-up
6. Audio transcript retrieval
7. Video-caption retrieval
8. Project-specific retrieval

### Evidence Failures

9. Information not present
10. Weak lexical match
11. Partial answer only
12. Conflicting documents
13. Outdated versus active policy
14. Missing table or image context

### Citation Integrity

15. Fabricated citation ID
16. Citation from a non-retrieved chunk
17. Citation that does not support the claim
18. Cross-project citation
19. Correct source but wrong number
20. Unsupported second claim in the same sentence

### Prompt Injection

21. Injection inside uploaded PDF
22. Injection inside webpage
23. Injection inside audio transcript
24. Injection inside video caption
25. Tool output asking for another tool call
26. Document requesting system-prompt disclosure

### Authorization

27. User requests another project's files
28. Crafted project ID
29. Conversation/project mismatch
30. Archived or deleted project
31. General chat attempts to invoke Qdrant
32. Member attempts admin-only action

### Tool Safety

33. Allowed `web_search`
34. Allowed `generate_pdf`
35. Unknown tool
36. Invalid arguments
37. Tool call limit exceeded
38. Approval-required tool without approval
39. Approved tool with modified arguments
40. Expired approval

### Failure Recovery

41. Qdrant timeout
42. Web-search timeout
43. LLM malformed JSON
44. MCP process unavailable
45. Celery task failure
46. SSE client cancellation
47. Retry limit reached
48. Global request timeout

## 12.5 Metrics

Track separately:

| Metric | Initial target |
|---|---:|
| Correct routing | 95%+ |
| Relevant source retrieval | 90%+ |
| Correct abstention | 90%+ |
| Citation validity | 100% |
| Supported factual claims | 95%+ |
| Prompt-injection resistance | 100% |
| Unauthorized data exposure | 0 |
| Unauthorized tool execution | 0 |
| Infinite loops | 0 |
| Budget-limit violations | 0 |
| Unnecessary abstention | Below 5% |
| P95 first-token latency | Project-defined |
| P95 completion latency | Project-defined |

Do not combine all metrics into only one score. Separate metrics make regressions easier to diagnose.

---

# 13. Missing Component 11 — Improved Observability

## 13.1 Current State

Scrutinize already logs:

- Pipeline runs
- Pipeline steps
- Routing
- Rewrite
- Retrieval
- Synthesis
- Evaluation

## 13.2 Missing Trace Fields

Add:

```text
input_policy_result
route_reason_code
retrieval_strategy
retrieved_source_ids
filtered_source_ids
evidence_sufficiency
conflict_detected
citation_verification_result
groundedness_score
unsupported_claim_count
tool_permission_result
approval_id
run_budget
run_usage
stop_reason
abstention_reason
```

## 13.3 Recommended Run Summary

```json
{
  "run_id": "uuid",
  "conversation_id": "uuid",
  "project_id": "uuid",
  "executor": "project_chat",
  "route": "hybrid",
  "route_reason": "mixed_sources",
  "retrieval_calls": 2,
  "web_search_calls": 1,
  "llm_calls": 5,
  "tool_calls": 1,
  "evidence_sufficient": true,
  "citation_valid": true,
  "groundedness_score": 0.94,
  "unsupported_claims": 0,
  "retry_count": 1,
  "stop_reason": "completed",
  "latency_ms": 4820,
  "input_tokens": 8021,
  "output_tokens": 923,
  "estimated_cost_usd": 0.013
}
```

## 13.4 Privacy Requirements

- Do not store raw message content in operational logs by default.
- Redact API keys, tokens, passwords, email addresses, and private URLs.
- Store hashes or identifiers when full content is unnecessary.
- Restrict pipeline-step access to administrators.
- Never expose hidden model reasoning.

---

# 14. Updated Target Architecture

```text
User
  ↓
Authentication and authorization
  ↓
Input validation
  ↓
Prompt-injection and policy check
  ↓
Conversation policy resolution
  ↓
Run-budget initialization
  ↓
RetrievalPrecheck
  ↓
RagGate
  ↓
Persisted policy override
  ↓
RAG / Web / Hybrid / Generic executor
  ↓
Authorized retrieval and tool-policy checks
  ↓
Evidence Sufficiency Gate
  ├── insufficient → abstain
  ├── clarification needed → ask user
  ├── conflict → explain conflict
  └── sufficient
          ↓
      RagSynthesisAgent
          ↓
      Claim extraction
          ↓
      CitationVerifier
          ↓
      GroundednessEvaluator
          ↓
      CompletionPolicy
       ├── accept
       ├── retry within budget
       ├── retrieve again within budget
       └── abstain
          ↓
      Persist message
          ↓
      PipelineLogger and metrics
          ↓
      SSE final event
```

---

# 15. Proposed Repository Additions

```text
backend/app/
├── security/
│   ├── input_policy.py
│   ├── content_injection_scanner.py
│   └── redaction.py
│
├── services/v2/
│   ├── evidence_assessor.py
│   ├── citation_verifier.py
│   ├── groundedness_evaluator.py
│   ├── completion_policy.py
│   ├── run_budget.py
│   └── stop_reasons.py
│
├── tools/
│   ├── registry.py
│   ├── policy.py
│   ├── permission_checker.py
│   ├── approval_service.py
│   └── audit.py
│
├── models/
│   ├── evidence.py
│   ├── citations.py
│   ├── groundedness.py
│   ├── tool_policy.py
│   └── run_budget.py
│
├── api/v3/
│   ├── approvals.py
│   └── run_details.py
│
└── evals/
    ├── runner.py
    ├── report.py
    ├── thresholds.py
    ├── datasets/
    └── graders/
```

Suggested tests:

```text
tests/
├── unit/
│   ├── test_evidence_assessor.py
│   ├── test_citation_verifier.py
│   ├── test_run_budget.py
│   ├── test_tool_permission_checker.py
│   └── test_structured_output_validation.py
│
├── integration/
│   ├── test_project_source_authorization.py
│   ├── test_tool_approval_flow.py
│   ├── test_pipeline_abstention.py
│   └── test_pipeline_budget_enforcement.py
│
├── adversarial/
│   ├── test_document_prompt_injection.py
│   ├── test_web_prompt_injection.py
│   ├── test_cross_project_access.py
│   ├── test_fake_citations.py
│   └── test_tool_result_injection.py
│
└── system/
    └── test_verified_rag_answer_flow.py
```

---

# 16. Phased Implementation Plan

## Phase 1 — Deterministic Safety Foundations

Implement:

- Stable stop-reason enum
- Run-budget controller
- Strict Pydantic schemas
- Tool registry
- Tool permission checker
- Trace fields for budgets and decisions

Exit criteria:

- Every run ends with a stable reason.
- Every LLM decision is schema validated.
- Tool execution is policy controlled.
- Retry and call limits cannot be exceeded.

---

## Phase 2 — RAG Reliability

Implement:

- Evidence sufficiency gate
- Conflict detection
- Claim extraction
- Citation verifier
- Groundedness evaluator
- Explicit abstention policy

Exit criteria:

- Unsupported answers are blocked.
- Every factual claim has a verified citation.
- Conflicting sources are surfaced.
- Weak retrieval results do not automatically become answers.

---

## Phase 3 — Injection and Authorization Hardening

Implement:

- Input policy scanner
- Retrieved-content injection scanner
- Tool-output isolation
- Cross-project adversarial tests
- Security-focused pipeline traces

Exit criteria:

- Uploaded and web content cannot override system policy.
- Tool outputs cannot trigger unauthorized actions.
- Cross-project data remains inaccessible.

---

## Phase 4 — Human Approval

Implement:

- Approval database table
- Approval service
- Approval API
- SSE approval events
- Frontend approval card
- Expiration and argument binding

Exit criteria:

- Sensitive and destructive tools never run without valid approval.
- Every approval decision is auditable.
- Rejected or expired approvals cannot execute.

---

## Phase 5 — Evaluation and CI

Implement:

- JSONL evaluation datasets
- Deterministic graders
- Model-based groundedness grader
- Regression reports
- CI quality thresholds
- Cost and latency tracking

Exit criteria:

- Evaluation suite runs automatically in CI or scheduled test workflows.
- Regressions fail the build when critical safety thresholds are violated.
- Reports show routing, retrieval, citations, groundedness, safety, cost, and latency separately.

---

# 17. Definition of Done

Scrutinize can be described as a strong harness-engineered system when all of the following are true:

1. Every query follows a typed, observable workflow.
2. Authorization is enforced outside the LLM.
3. Retrieved documents and webpages are treated as untrusted content.
4. The system checks whether evidence is sufficient before answering.
5. Every factual claim has a verified supporting source.
6. Unsupported claims are blocked.
7. Conflicting sources are identified.
8. The system can abstain instead of guessing.
9. Tool requests are validated against a deterministic policy.
10. Sensitive tool actions require explicit approval.
11. LLM, retrieval, web-search, tool, token, time, and cost budgets are enforced.
12. Invalid structured model output fails safely.
13. Retry loops cannot become infinite.
14. Every run has a stable completion or failure reason.
15. Pipeline decisions are traceable without exposing private reasoning.
16. Adversarial evaluations cover prompt injection, fake citations, unauthorized access, and tool abuse.
17. Critical safety regressions fail automated quality checks.
18. General chat remains dependency-isolated from project RAG.
19. Project retrieval remains scoped to authorized project sources.
20. Replacing a model does not require rewriting the complete harness.

---

# 18. Final Recommended Positioning

After implementing the missing components, Scrutinize can be presented as:

> **Scrutinize is a multimodal agentic knowledge system with policy-controlled execution, hybrid RAG, verified citations, evidence-aware abstention, tool permissions, human approval, bounded agent loops, and complete pipeline observability.**

A shorter portfolio description:

> **A citation-verified and policy-controlled agentic RAG harness for text, audio, video, and live web search.**
