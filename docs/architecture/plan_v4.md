# Scrutinize V4 Implementation Plan

**Objective:** Implement the V4 system architecture by combining Scrutinize's validation harness needs with modern 2026 AI libraries (PydanticAI, Burr, Letta, Phoenix, E2B, Exa, DeepEval, Promptfoo).

---

## Phase 1: Security & Orchestration Infrastructure

### 1.1. Core Orchestration with Apache Burr & PydanticAI
* **Task 1:** Install dependencies: `pip install burr pydantic-ai`.
* **Task 2:** Create [burr_orchestrator.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v3/burr_orchestrator.py) to manage RAG agent execution states.
* **Task 3:** Define PydanticAI schemas in [schemas/v3/](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/schemas/v3/) for routing classification (`GateResult`), query rewriting, evidence assessment, citation mapping, and groundedness metrics.
* **Task 4:** Refactor the gate model logic using PydanticAI's structured model outputs, replacing the regex JSON parsing in `json_utils.py`.

### 1.2. Central Run-Budget Controller
* **Task 1:** Implement [run_budget.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v3/run_budget.py) to enforce budgets (max 2 RAG attempts, 6 LLM calls, 2 web searches, 3 tools, and 20,000 input tokens).
* **Task 2:** Track execution metrics dynamically within the Burr state machine. If any limit is crossed, immediately halt the run and return `StopReason.budget_exceeded`.

### 1.3. OpenTelemetry Tracing with Phoenix
* **Task 1:** Install Arize Phoenix tracing: `pip install openinference-instrumentation-openai phoenix`.
* **Task 2:** Add initialization code to `main.py` to start tracing with Phoenix and OpenInference.
* **Task 3:** Instrument [burr_orchestrator.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v3/burr_orchestrator.py) steps to export traces containing token counts, route classifications, validation verdicts, and database timings.

### 1.4. Phase 1 Exit Criteria
* All FastAPI search requests route through the Burr state machine.
* Any structured output is typed and verified using PydanticAI models.
* Token count and call budgets are successfully tracked, and exceeding them triggers a clean failure.
* Complete visual trace logs of agent steps are inspectable in the local Phoenix dashboard.

---

## Phase 2: RAG Quality & Citation Validation Harness

### 2.1. Evidence Sufficiency Gate
* **Task 1:** Implement [evidence_assessor.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v3/evidence_assessor.py) using PydanticAI to evaluate if the retrieved chunks contain enough details to answer the query.
* **Task 2:** If the assessor detects insufficient info, trigger `StopReason.insufficient_evidence` and return a clean abstention message instead of generating a hallucinated answer.

### 2.2. Citation Verifier & Groundedness Evaluator
* **Task 1:** Write [citation_verifier.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v3/citation_verifier.py) to parse cited source IDs from synthesis draft responses.
* **Task 2:** Verify that:
  1. The citation ID exists in the active Qdrant retrieval list.
  2. The chunk content supports the claim.
* **Task 3:** Write [groundedness_evaluator.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v3/groundedness_evaluator.py) to score the generated answer. If the score is below `0.90`, trigger a single regeneration loop inside Burr.

### 2.3. Temporal & Persistent Memory Integration
* **Task 1:** Integrate **Letta** client into [memory_manager.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v3/memory_manager.py) to manage long-term user/project memory partitions.
* **Task 2:** Set up **Graphiti** to index project files into an evolving temporal knowledge graph, matching dates and relationships to resolve outdated facts.

### 2.4. Phase 2 Exit Criteria
* The RAG engine abstains cleanly rather than guessing when evidence is missing.
* Drafts containing fabricated citations or ungrounded claims are automatically caught and regenerated.
* Long-term user memories persist across different conversations.

---

## Phase 3: Sandboxed Execution & Tool Permissions

### 3.1. Tool Policy & Permission Checker
* **Task 1:** Write [tools/policy.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/tools/policy.py) mapping tools (`web_search`, `generate_pdf`, etc.) to risk levels and role requirements.
* **Task 2:** Implement a deterministic `PermissionChecker` that intercepts agent requests before they reach the tool execution layer.

### 3.2. E2B Sandbox Isolation
* **Task 1:** Sign up for E2B and install client: `pip install e2b`.
* **Task 2:** Create [tools/execution_sandbox.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/tools/execution_sandbox.py) to launch throwaway E2B Sandboxes (Firecracker MicroVMs) for running python code generated by the agent.

### 3.3. Human Approval Gate
* **Task 1:** Add a `tool_approvals` table in Neon Postgres.
* **Task 2:** If a tool requires approval, write a record with status `waiting` and pause the Burr state machine.
* **Task 3:** Expose FastAPI v3 endpoints `/v3/approvals/pending` and `/v3/approvals/{id}/decide`.
* **Task 4:** Emit `approval.required` via SSE connection. When the user approves, resume the Burr execution thread.

### 3.4. Phase 3 Exit Criteria
* All code execution tool calls run in isolated E2B microVM sandboxes.
* Role-based permissions are enforced.
* Sensitive tool actions block, emit an SSE notification, and wait for explicit human approval before running.

---

## Phase 4: CI/CD Quality Evals & Red-Teaming

### 4.1. RAG Evals with DeepEval
* **Task 1:** Install DeepEval: `pip install deepeval`.
* **Task 2:** Create [evals/runner.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/evals/runner.py) to run test cases.
* **Task 3:** Create evaluation datasets under `evals/datasets/` in JSONL format, covering routing accuracy, groundedness, and retrieval.
* **Task 4:** Configure GitHub Actions to run DeepEval tests and fail the build if groundedness falls below `0.90`.

### 4.2. Security Audits with Promptfoo
* **Task 1:** Install Promptfoo: `npm install -g promptfoo`.
* **Task 2:** Create `promptfooconfig.yaml` in the backend root to test for prompt injections, system disclosure, and unauthorized cross-project access.
* **Task 3:** Add Promptfoo red-teaming checks to the CI/CD pipeline.

### 4.3. Phase 4 Exit Criteria
* PR builds fail automatically if safety thresholds are breached.
* System routing and RAG quality metrics are systematically measured on check-in.

---

## Phase 5: Frontend UI Upgrades

### 5.1. SSE Pipeline Steps
* **Task 1:** Update the React chat UI to listen to SSE state broadcasts from Burr.
* **Task 2:** Render loading states reflecting the validation steps (e.g., "Verifying citations...", "Assessing evidence...").

### 5.2. Tool Approval Component
* **Task 1:** Design a visual approval card in [Sidebar.tsx](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/frontend/src/components/Sidebar.tsx) or the chat panel when the `approval.required` event is received.
* **Task 2:** Include buttons to `Approve` or `Reject` the tool arguments, linking to `/v3/approvals/{id}/decide`.

### 5.3. Phase 5 Exit Criteria
* Users can view visual step-by-step progress of the validation harness.
* Users can review tool arguments and click to approve/reject sensitive actions inline.
