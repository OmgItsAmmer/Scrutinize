# Scrutinize v2 — Implementation Log

Progress log for the **local LLM + agentic RAG pipeline** on branch `v2/local-llm-pipeline`.  
Plan reference: [`docs/plan_v2.md`](./plan_v2.md). v1 (`main`) `/search` pipeline is unchanged.

---

## Branch strategy

| Branch | Status |
|---|---|
| `main` | Frozen — OpenAI router/synthesis, `POST /search` |
| `v2/local-llm-pipeline` | Active — local Qwen pipeline, `POST /v2/search` |

New v2 code lives under `backend/app/services/v2/` and `backend/app/api/v2/` so both pipelines coexist.

---

## Phase 0 — Branch setup, config, local LLM client (M0, M1, M6)

**Goal:** Config, HTTP client for Ollama/ngrok `/api/generate`, v2 API scaffold, health probe.

| Task | File(s) |
|---|---|
| v2 env settings (`LOCAL_LLM_*`, `V2_*`) | `backend/app/core/config.py` |
| Example env vars documented | `.env.example` |
| Ollama-compatible LLM client (ngrok header, URL normalization, `thinking` fallback) | `backend/app/services/v2/local_llm_client.py` |
| v2 package exports | `backend/app/services/v2/__init__.py` |
| FastAPI v2 router mount (`/v2`) | `backend/app/api/v2/router.py`, `backend/app/api/router.py` |
| LLM health probe `GET /v2/llm-health` | `backend/app/api/v2/llm_health.py` |
| Health response schema | `backend/app/schemas/v2/llm_health.py` |
| v2 schemas package | `backend/app/schemas/v2/__init__.py` |
| DI: `get_local_llm_client` | `backend/app/core/deps.py` |
| `@pytest.mark.v2` marker | `pytest.ini`, `backend/pyproject.toml` |
| CI v2 unit test step | `.github/workflows/ci.yml` |
| Test env default for LLM URL | `tests/conftest.py` |

**Deliverable:** `LocalLlmClient` talks to ngrok/Ollama; `/v2/llm-health` pings gate model; v1 `/health` untouched.

---

## Phase 1 — Query rewriter & RAG gate (M6, M7)

**Goal:** Rewriter → gate → generic reply or RAG path; `POST /v2/search` wired.

| Task | File(s) |
|---|---|
| Query rewriter (`qwen3.5:2b`) | `backend/app/services/v2/query_rewriter.py` |
| RAG gate (`qwen3.5:0.8b`, JSON parse, default to `rag` on failure) | `backend/app/services/v2/rag_gate.py` |
| Generic reply agent (`qwen3.5:0.8b`) | `backend/app/services/v2/generic_agent.py` |
| JSON parsing helper (fenced code blocks) | `backend/app/services/v2/json_utils.py` |
| System prompts | `backend/app/services/v2/prompts/query_rewriter_system.txt` |
| | `backend/app/services/v2/prompts/rag_gate_system.txt` |
| | `backend/app/services/v2/prompts/generic_agent_system.txt` |
| Prompt loader | `backend/app/services/v2/prompts/__init__.py` |
| v2 search API `POST /v2/search` | `backend/app/api/v2/search.py` |
| Request/response schemas | `backend/app/schemas/v2/search.py` |
| DI: rewriter, gate, generic, orchestrator | `backend/app/core/deps.py` |

**Deliverable:** Generic chitchat works end-to-end; indexed-content queries enter RAG path.

---

## Phase 2 — RRF retrieval & RAG synthesis (M5, M7)

**Goal:** Reciprocal Rank Fusion + local LLM synthesis over retrieved chunks.

| Task | File(s) |
|---|---|
| RRF fusion math + Qdrant hit → `SearchSource` | `backend/app/services/v2/retrieval_utils.py` |
| RRF retriever (rewritten + original query lists, top 5) | `backend/app/services/v2/rrf_retriever.py` |
| RAG synthesis agent (`qwen3.5:2b`) | `backend/app/services/v2/rag_synthesis_agent.py` |
| Synthesis system prompt | `backend/app/services/v2/prompts/rag_synthesis_system.txt` |
| DI: `get_rrf_retriever`, `get_rag_synthesis_agent` | `backend/app/core/deps.py` |
| Prompt `.txt` files bundled in package | `backend/pyproject.toml` (`package-data`) |

**Reused unchanged (v1):** `backend/app/services/embedding_service.py`, `backend/app/services/vector_store.py`

**Deliverable:** RAG queries return grounded answer + up to 5 source segments.

---

## Phase 3 — Decision agent & retry loop (M7)

**Goal:** `qwen3.5:4b` scores each draft answer; retry up to 2 times; append disclaimer on low confidence.

| Task | File(s) |
|---|---|
| Decision agent (`qwen3.5:4b`, JSON verdict + confidence + feedback) | `backend/app/services/v2/decision_agent.py` |
| Decision system prompt | `backend/app/services/v2/prompts/decision_agent_system.txt` |
| Orchestrator retry loop (max `V2_MAX_PIPELINE_ATTEMPTS`, threshold `V2_CONFIDENCE_THRESHOLD`) | `backend/app/services/v2/pipeline_orchestrator.py` |
| Low-confidence disclaimer text | `backend/app/services/v2/pipeline_orchestrator.py` (`LOW_CONFIDENCE_DISCLAIMER`) |
| Structured attempt logging (JSON) | `backend/app/services/v2/pipeline_orchestrator.py` |
| DI: `get_decision_agent` | `backend/app/core/deps.py` |
| Response fields: `attempts`, `confidence`, `disclaimer_appended` | `backend/app/schemas/v2/search.py` (already defined in Phase 1) |

**Retry behaviour:**
- Confidence ≥ `V2_CONFIDENCE_THRESHOLD` (default `0.7`) → return answer immediately
- Below threshold on attempt 1 → pass `feedback` to rewriter and re-run full pipeline
- Below threshold after final attempt → append *"Note: answer may vary — retrieval confidence was low."*

**Deliverable:** Full v2 backend pipeline complete through decision loop.

---

## Phase 4 — Frontend & API contract (M7, M8)

**Goal:** Wire React UI to `POST /v2/search`; show route, confidence, attempts, disclaimer; conversation memory.

| Task | File(s) |
|---|---|
| `SearchV2Response` TypeScript type | `frontend/src/types/api.ts` |
| Env-driven search path (`VITE_SEARCH_API`, default `/v2/search`) | `frontend/src/api/client.ts`, `frontend/src/vite-env.d.ts` |
| App state uses v2 search result + `conversation` | `frontend/src/context/AppContext.tsx` |
| Route chip, confidence badge, attempts, disclaimer footnote | `frontend/src/components/SourceCard.tsx` (`SearchResults`) |
| Loading message (generic vs library search latency) | `frontend/src/components/SearchView.tsx` |
| Answer/disclaimer display helpers | `frontend/src/lib/format.ts` |

---

## Phase 4b — Generic fast-path & conversation memory

**Goal:** Faster generic replies; rolling 10-message context with summarization.

| Task | File(s) |
|---|---|
| Gate returns `reply` for generic; skip rewriter + decision on generic path | `backend/app/services/v2/rag_gate.py`, `prompts/rag_gate_system.txt` |
| Generic fast-path in orchestrator (1× 0.8b call) | `backend/app/services/v2/pipeline_orchestrator.py` |
| Conversation window + LLM summarization | `backend/app/services/v2/conversation_memory.py` |
| Context injected into all agents | `query_rewriter.py`, `rag_synthesis_agent.py`, `decision_agent.py`, `generic_agent.py` |
| `ConversationState` on request/response | `backend/app/schemas/v2/search.py` |
| Config `V2_CONVERSATION_WINDOW_SIZE` (default 10) | `backend/app/core/config.py` |
| Frontend sends/receives `conversation` | `frontend/src/api/client.ts`, `AppContext.tsx` |

**Generic path (fast):** Gate (0.8b) → return `reply` immediately — no rewriter, generic agent, or decision agent.

**Conversation:** Last 10 messages kept; when exceeded, older block summarized via 2b model; all summaries retained for context.

---

## Current v2 pipeline flow

```text
User query + conversation state
    │
    ▼
ConversationMemory.prepare()   conversation_memory.py
    │
    ▼
RagGate (0.8b) — classify + reply if generic
    │
    ├── generic ──► return gate.reply immediately (fast path)
    │
    └── rag ──► QueryRewriter → RRF → RagSynthesis → DecisionAgent (retry loop)
```

Orchestrated by `backend/app/services/v2/pipeline_orchestrator.py`  
Exposed at `POST /v2/search` via `backend/app/api/v2/search.py`  
Frontend: `frontend/src/api/client.ts` → `SearchView` / `SearchResults`

---

## Configuration (v2)

Set in `backend/.env` (documented in `.env.example`):

| Variable | Purpose |
|---|---|
| `LOCAL_LLM_BASE_URL` | ngrok/Ollama host (with or without `/api/generate`) |
| `LOCAL_LLM_REWRITER_MODEL` | Default `qwen3.5:2b` |
| `LOCAL_LLM_GATE_MODEL` | Default `qwen3.5:0.8b` |
| `LOCAL_LLM_DECISION_MODEL` | Default `qwen3.5:4b` |
| `LOCAL_LLM_TIMEOUT_S` | HTTP timeout |
| `V2_MAX_PIPELINE_ATTEMPTS` | Default `2` |
| `V2_CONFIDENCE_THRESHOLD` | Default `0.7` |
| `V2_RRF_K` | RRF constant, default `60` |
| `V2_RRF_NUM_LISTS` | Default `2` (rewritten + original) |
| `V2_RRF_TOP_K` | Fused top segments, default `5` |
| `VITE_SEARCH_API` | Frontend search path, default `/v2/search` |

Embeddings still use OpenAI via `backend/app/services/embedding_service.py` (`OPENAI_API_KEY`).

---

## Tests added

| File | Covers |
|---|---|
| `tests/unit/test_local_llm_client.py` | LLM client, URL normalization, ngrok headers, thinking fallback |
| `tests/unit/test_v2_llm_health.py` | `GET /v2/llm-health` |
| `tests/unit/test_v2_agents.py` | Rewriter, RAG gate, JSON utils |
| `tests/unit/test_v2_pipeline.py` | Orchestrator generic / RAG / retry / disclaimer fallback |
| `tests/unit/test_v2_search_api.py` | `POST /v2/search` endpoint |
| `tests/unit/test_v2_rrf.py` | RRF fusion + retriever |
| `tests/unit/test_v2_rag_synthesis.py` | RAG synthesis agent |
| `tests/unit/test_v2_decision_agent.py` | Decision agent JSON parsing + chunk summaries |

Run: `pytest tests/unit -m v2`

---

## Not yet implemented

| Phase | What's left | Planned location |
|---|---|---|
| **Phase 5** | `architecture_v2.md`, module doc, demo script | `docs/` |
| **Deferred** | Qdrant → ChromaDB, Neon → SQLite | per `plan_v2.md` §11 |

---

## Quick verification commands

```bash
# LLM reachable via ngrok
curl http://localhost:8000/v2/llm-health

# Full v2 search (after uploading + indexing documents)
curl -X POST http://localhost:8000/v2/search \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"How much garlic in the pasta recipe?\"}"
```

Response includes `attempts`, `confidence`, and `disclaimer_appended` when the decision agent runs.
