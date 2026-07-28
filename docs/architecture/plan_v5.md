# Scrutinize V5 Implementation Plan — Retrieval Quality & Production Hardening

**Objective:** V4 built a validation harness *around* the pipeline (Burr state machine, typed outputs, run budgets, evidence/citation/groundedness gates, tool policy + approvals). V5 fixes what feeds that harness. Every V4 gate is downstream of retrieval; improving retrieval raises the pass rate of every gate and reduces regeneration loops rather than adding more machinery to catch failures after the fact.

**Scope boundary:** V5 changes ingestion, retrieval, and the operational layer. It does **not** restructure the Burr graph, replace the V4 gates, or add new agent frameworks.

---

## Module Map

| # | Module | Primary files | Phase |
|---|---|---|---|
| M0 | Golden dataset & retrieval metrics | `backend/app/evals/` | 0 |
| M1 | Candidate pool widening | `vector_store.py`, `rrf_retriever.py` | 1 |
| M2 | Cross-encoder reranker | `services/v5/reranker.py` | 1 |
| M3 | Structured document parsing (Docling) | `services/parsing/` | 2 |
| M4 | Page-aware segments | `models/segment.py`, `schemas/search.py`, migration 016 | 2 |
| M5 | OCR fallback | `services/parsing/ocr.py` | 2 |
| M6 | Contextual chunk headers | `services/v5/context_enricher.py` | 3 |
| M7 | Reindex / backfill job | `workers/tasks.py` | 3 |
| M8 | Token & cost accounting | `pipeline_logger.py`, `run_budget.py`, migration 017 | 4 |
| M9 | Content-hash dedup | `models/file.py`, `ingestion.py`, migration 018 | 4 |
| M10 | Redis embedding cache | `services/embedding_service.py` | 4 |
| M11 | Qdrant tenancy & quantization | `services/vector_store.py` | 4 |
| M12 | Untrusted-content envelope | `services/v5/untrusted.py` | 5 |
| M13 | Tool-intent provenance | `tools/policy.py`, `burr_orchestrator.py` | 5 |
| M14 | SSE concurrency refactor | `api/v3/conversations.py` | 6 |
| M15 | CI eval & red-team gating | `.github/workflows/`, `promptfooconfig.yaml` | 7 |

---

## Phase 0: Measurement Baseline

**Rationale:** This phase is deliberately placed first, ahead of the ordering discussed, and is deliberately *small*. Phase 1 and Phase 3 are quality claims — without a baseline captured **before** they land, "the reranker helped" is unfalsifiable. This is the dataset only. The full eval framework stays in Phase 7.

### M0.1 Golden dataset
* **Task 1:** Create `backend/app/evals/datasets/retrieval_golden.jsonl`. 40–60 real queries drawn from `pipeline_runs.original_query` in production, each annotated with the `file_id`(s) and ideally `segment_id`(s) that *should* be retrieved.
* **Task 2:** Cover the distribution deliberately: RAG-route queries, generic-route queries, queries that should abstain (no supporting evidence in corpus), multi-hop queries, keyword-heavy queries (names, IDs, exact terms), and paraphrase queries. The abstention cases matter — they are what stop a reranker from being tuned into overconfidence.
* **Task 3:** Commit a fixture project + seed script so the dataset is reproducible: `backend/scripts/seed_eval_corpus.py`.

### M0.2 Retrieval metrics harness
* **Task 1:** Create `backend/app/evals/retrieval_metrics.py` computing **Recall@k**, **MRR**, and **nDCG@k** against the golden set. Plain functions, no framework dependency.
* **Task 2:** Create `tests/evals/test_retrieval_baseline.py` (pytest marker `evals`, excluded from default CI run) that executes the dataset through `RrfRetriever` and writes results to `backend/app/evals/results/<git-sha>.json`.
* **Task 3:** Record the **baseline numbers on current `main`** and commit them as `backend/app/evals/results/baseline.json`.

### Phase 0 Exit Criteria
* `pytest tests/evals -m evals` runs end to end and emits Recall@5, MRR, nDCG@5.
* A committed baseline exists that Phases 1–3 will be measured against.

---

## Phase 1: Retrieval Precision

### M1: Candidate pool widening
**Problem:** [`vector_store.py:337`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/vector_store.py) issues both the dense and sparse prefetch with `limit=top_k`, and `RrfRetriever` passes `v2_rrf_top_k` (= 5). The system therefore fuses a 5-item dense list with a 5-item sparse list and returns 5. RRF over a pool that narrow contributes almost nothing, and there is no candidate surplus for a reranker to work with.

* **Task 1:** Split the parameter. Add `v2_rrf_prefetch_limit: int = 50` to [`config.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/core/config.py). Change `search_hybrid` to accept `prefetch_limit` (per-branch Qdrant `limit`) separately from `top_k` (post-fusion cut).
* **Task 2:** Update `fuse_rrf_hits` callers so fusion happens over the full prefetched lists, then truncates.
* **Task 3:** Extend `RetrievalStats` with `prefetch_limit` so traces show pool size vs. returned size.
* **Task 4:** Re-run Phase 0 metrics. **Expect a measurable Recall@5 gain from this task alone**, before any reranker exists.

### M2: Cross-encoder reranker
* **Task 1:** Create [`backend/app/services/v5/reranker.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v5/reranker.py) exposing `Reranker.rerank(query: str, sources: list[SearchSource], top_k: int) -> list[RerankedSource]`.
* **Task 2:** Back it with `fastembed`'s cross-encoder support (`bge-reranker-v2-m3` or `jina-reranker-v2-base`). **No new service** — `fastembed` is already a dependency for BM25 sparse vectors. Lazy-load the model exactly as `VectorStore.sparse_model` does, so worker startup is unaffected.
* **Task 3:** Add settings: `rerank_enabled: bool = True`, `rerank_model: str`, `rerank_candidate_pool: int = 50`, `rerank_top_k: int = 5`, `rerank_timeout_s: float = 5.0`.
* **Task 4:** Wire into `RrfRetriever.retrieve` as a post-fusion stage: retrieve `rerank_candidate_pool` → rerank → return `rerank_top_k`. Preserve the pre-rerank rank on each source (`rrf_rank`) alongside `rerank_score` so the trace shows what moved.
* **Task 5:** **Fail open.** If the model fails to load or the rerank exceeds `rerank_timeout_s`, log a warning and return the RRF order unchanged. Reranking is an improvement, never a new failure mode.
* **Task 6:** Emit rerank latency and score deltas to `pipeline_steps` (`step_type='rerank'`) and the Phoenix trace.

### M2.1 Interaction with the V4 harness
* **Task 1:** Confirm `EvidenceAssessor`, `CitationVerifier` and `GroundednessEvaluator` consume the reranked list.
* **Task 2:** Record `insufficient_evidence` and regeneration-loop rates before and after. The expected outcome is these *drop* — that is the mechanism by which this change pays for itself.

### Phase 1 Exit Criteria
* Prefetch pool and final `top_k` are independently configurable and traced.
* Reranking is on by default, degrades gracefully, and adds < 300ms p95.
* Recall@5 / MRR / nDCG@5 improve measurably against `baseline.json`.
* `insufficient_evidence` abstention rate and V4 regeneration count both decrease.

---

## Phase 2: Document Understanding

**Problem:** [`text_processor.py:29`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/text_processor.py) joins every PDF page into one string and slices fixed 400-token windows. Page boundaries, headings and table structure are destroyed before embedding, no positional metadata survives, and image captions are appended after all text chunks — orphaned from their page.

### M3: Structured parsing via Docling
* **Task 1:** Create `backend/app/services/parsing/` with a `DocumentParser` protocol: `parse(path) -> ParsedDocument` where `ParsedDocument` carries `blocks: list[ContentBlock]` and each block has `text`, `page_number`, `section_path`, `block_type` (`paragraph | heading | table | list | caption`).
* **Task 2:** Implement `parsing/docling_parser.py`. Docling is Apache-2.0, runs locally, and emits markdown with **table structure and page numbers** — which resolves M4's metadata requirement in the same pass.
* **Task 3:** Implement `parsing/pypdf_parser.py` preserving today's behaviour as a fallback, selected by `parser_backend: Literal["docling","pypdf"] = "docling"`.
* **Task 4:** Docling is a heavy dependency — install it in the **worker** image only. Verify the API container image size is unaffected.

### M4: Structure-aware chunking + page-aware segments
* **Task 1:** Replace `chunk_text` with `chunk_blocks(blocks, chunk_size, overlap)` in `services/parsing/chunking.py`. Rules: never merge across a page boundary; never split a table row; treat headings as hard boundaries; carry `section_path` down to child chunks; emit a table as a single chunk when it fits, otherwise split by rows with the header repeated.
* **Task 2:** Migration `016_segment_positions.sql` — add to `segments`: `page_number INT NULL`, `section_path TEXT NULL`, `char_start INT NULL`, `char_end INT NULL`, `block_type TEXT NULL`.
* **Task 3:** Extend [`models/segment.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/models/segment.py) and `VectorSegment` in `vector_store.py` with the same fields, and add them to the Qdrant payload.
* **Task 4:** Extend `SearchSource` in [`schemas/search.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/schemas/search.py) with `page_number` and `section_path`; populate in `hit_to_source`.
* **Task 5:** Surface it. Update the synthesis citation format and the frontend source cards to render "p. 7 — §2.1 Payment Terms". *This is the user-visible payoff of the whole phase — do not stop at the schema change.*

### M5: OCR fallback for scanned PDFs
* **Task 1:** Add a text-density check after parsing: if extracted characters per page < `ocr_min_chars_per_page` (default 100), classify the document as scanned.
* **Task 2:** Implement `parsing/ocr.py` — Docling's built-in OCR pipeline, or `ocrmypdf`/tesseract as a subprocess. Gate on `ocr_enabled: bool = True`.
* **Task 3:** Replace the current silent failure at [`text_processor.py:143`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/text_processor.py) (`"Text/PDF file has no text content"` → `FileStatus.FAILED`) with a distinct, user-facing status. If OCR also yields nothing, fail with a specific message ("this PDF appears to be a scanned image and text could not be extracted") rather than a generic ingestion error.
* **Task 4:** Add `tests/unit/test_ocr_fallback.py` with a genuinely image-only PDF fixture.

### M6 (in this phase): Image caption anchoring
* **Task 1:** Fix the orphaned-caption bug at [`text_processor.py:130`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/text_processor.py). Captions are currently produced in page order but appended as one flat list after all text chunks.
* **Task 2:** Emit each caption as a `ContentBlock` with `block_type='caption'` at its true `page_number`, so it chunks and cites like any other block.

### Phase 2 Exit Criteria
* PDFs parse into page- and section-anchored blocks; tables survive as coherent units.
* Every text segment carries `page_number`; citations in the UI display it.
* Scanned PDFs ingest via OCR, or fail with an accurate, specific message.
* Image captions are positioned at their originating page.

---

## Phase 3: Contextual Retrieval

**Rationale:** A chunk stripped of its document context embeds poorly — "the rate increased to 4.2%" is unretrievable without knowing which report, which quarter, which metric. Prepending a short generated context line before embedding is a one-time ingest cost with a large, published retrieval gain.

### M6: Context enricher
* **Task 1:** Create [`backend/app/services/v5/context_enricher.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v5/context_enricher.py): given the whole document plus one chunk, generate a 1–2 sentence situating header.
* **Task 2:** **Cache the document prefix.** The full document is identical across every chunk in a file — send it once as a cached prefix and vary only the chunk. Without this the phase is expensive; with it, it is cents per file. Verify the cache is actually being hit by logging cached vs. uncached input tokens (M8 makes this measurable).
* **Task 3:** For documents exceeding `contextual_max_doc_tokens` (default 100k), fall back to a `section_path` + document-title header assembled from M4 metadata with no LLM call.
* **Task 4:** Store the generated header in a separate `context_header` field. **Embed `context_header + "\n\n" + content`, but keep `content` clean for display and citation verification** — the V4 `CitationVerifier` must check claims against the original text, not against generated context.
* **Task 5:** Include the header in `build_sparse_index_text` so BM25 benefits too.
* **Task 6:** Settings: `contextual_retrieval_enabled: bool = True`, `contextual_context_model: str`, `contextual_max_doc_tokens: int = 100000`.

### M7: Reindex / backfill
* **Task 1:** Add a `reindex_file` Celery task in [`workers/tasks.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/workers/tasks.py) that re-parses, re-chunks, re-enriches and re-embeds an existing file, then atomically swaps its vectors (upsert new → delete old by `file_id`).
* **Task 2:** Add `backend/scripts/reindex_project.py` for staged per-project rollout.
* **Task 3:** Record a `pipeline_version` on segments so mixed-generation corpora are diagnosable during rollout.

### Phase 3 Exit Criteria
* New ingests carry context headers; embedding text and display text are distinct.
* Existing corpora can be reindexed per-project without downtime.
* Phase 0 metrics improve again over the Phase 1 result; cost per file is measured and documented.

---

## Phase 4: Operational Layer

### M8: Token & cost accounting
* **Task 1:** Migration `017_run_cost_accounting.sql` — add to `pipeline_steps`: `prompt_tokens INT`, `completion_tokens INT`, `cached_tokens INT`, `cost_usd NUMERIC(10,6)`; add to `pipeline_runs`: `total_cost_usd NUMERIC(10,6)`, `total_tokens INT`, `project_id UUID`.
* **Task 2:** Create `backend/app/services/v5/cost_model.py` with a per-model price table (input / cached-input / output per 1M tokens) and `estimate_cost(model, usage) -> Decimal`. Keep prices in one place; they change.
* **Task 3:** Capture `response.usage` at every LLM and embedding call site and thread it into [`pipeline_logger.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v2/pipeline_logger.py), which currently records no usage at all.
* **Task 4:** Extend [`run_budget.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v4/run_budget.py) with `max_cost_usd: float = 0.25` and a `cost_usd` counter, raising the existing `BudgetExceededError`. It currently caps calls but not spend, so one expensive model swap silently changes the economics of every run.
* **Task 5:** Add `GET /v3/projects/{id}/usage` returning cost aggregated by day and by model.

### M9: Content-hash dedup
* **Task 1:** Migration `018_file_content_hash.sql` — `files.content_sha256 TEXT NULL`, with a non-unique index and a partial unique index on `(project_id, content_sha256)`.
* **Task 2:** Compute sha256 during upload in [`services/ingestion.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/ingestion.py) / `upload_utils.py`.
* **Task 3:** On a duplicate within the same project, skip ingestion and return the existing `file_id` with a `duplicate_of` field. Duplicate chunks are actively harmful — they crowd diverse results out of top-k and RRF rewards the same content twice.
* **Task 4:** Backfill script for existing rows.

### M10: Redis embedding cache
* **Task 1:** Wrap [`EmbeddingService.embed_texts`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/embedding_service.py) with a Redis cache keyed `emb:{model}:{sha256(text)}`. Redis is already in the stack for Celery.
* **Task 2:** Cache **query** embeddings aggressively (`embedding_cache_ttl_s = 86400`); repeated and near-repeated queries are common and this is the latency path.
* **Task 3:** Handle partial hits within a batch — fetch only the misses, preserve input ordering on reassembly.
* **Task 4:** Log hit rate. If it is below ~20% for queries, the cache is not earning its complexity.

### M11: Qdrant tenancy & quantization
* **Task 1:** In `_ensure_payload_indexes` ([`vector_store.py:112`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/vector_store.py)), create the `project_id` index with `is_tenant=True` (`KeywordIndexParams`). This physically co-locates each tenant's vectors on disk and matches your access pattern exactly — every query filters by `project_id`.
* **Task 2:** Enable scalar int8 quantization in `create_collection` (`ScalarQuantization`, `always_ram=True`) for ~4x memory reduction at negligible recall cost.
* **Task 3:** Both are collection-creation-time settings — **existing collections need a migration path.** Write `backend/scripts/migrate_qdrant_collection.py` (create new collection → re-upsert → alias swap) and treat this as a planned maintenance operation, not a config toggle.
* **Task 4:** Re-run Phase 0 metrics after quantization to confirm recall did not regress.

### Phase 4 Exit Criteria
* Every run has a persisted cost, attributable to a project.
* Spend is a first-class budget dimension alongside call counts.
* Re-uploads do not duplicate vectors.
* Query-embedding cache hit rate is measured; p95 retrieval latency drops.
* Tenant-optimized index and quantization live, with recall verified unchanged.

---

## Phase 5: Prompt-Injection Hardening

**Rationale:** Listed as gap #4 in `scrutinize_harness_missing_components.md` and still unimplemented (`grep -rn "injection"` returns only an unrelated comment). V4 raised the stakes: with [`tools/policy.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/tools/policy.py) and an approval gate now in place, a poisoned document that can influence tool selection is a privilege-escalation path, not just a bad answer. The defense is structural, not a classifier.

### M12: Untrusted-content envelope
* **Task 1:** Create `backend/app/services/v5/untrusted.py` with `wrap_untrusted(sources) -> str`, rendering retrieved chunks inside explicit delimiters with per-source IDs.
* **Task 2:** Update every synthesis prompt to state that delimited content is **data to be quoted and cited, never instructions to be followed**.
* **Task 3:** Strip or escape delimiter-lookalike sequences in retrieved text so a document cannot close the envelope and escape into instruction context.
* **Task 4:** Neutralize instruction-shaped patterns at ingest (`ignore previous instructions`, embedded `system:` / `assistant:` turns, hidden-text tricks) — flag on the segment rather than deleting, so the original document remains faithful.

### M13: Tool-intent provenance
* **Task 1:** Audit the Burr graph: establish which node decides tool invocation and whether retrieved text is in that node's context window. Document the finding — this determines how much of M13 is required.
* **Task 2:** Enforce that tool selection derives **only from the user turn and `client_requested_tool`**, never from retrieved or web content. Thread a `provenance` field through so `PermissionChecker` can reject any tool request not originating from a user turn.
* **Task 3:** Extend `PermissionChecker.check_permission` to take provenance as a required argument — make the unsafe call impossible to write rather than merely discouraged.
* **Task 4:** `execute_python` is `risk_level: high` / `requires_approval` — verify no path reaches [`execution_sandbox.py`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/tools/execution_sandbox.py) without an approval record.
* **Task 5:** **Remove the local `exec()` fallback** in `execute_python_in_sandbox`. When `E2B_API_KEY` is unset it currently runs model-generated code in-process on the API host with `exec()`. That is the single most dangerous line in the codebase; a missing env var should disable the tool, not silently downgrade its isolation.

### M14: Adversarial test suite
* **Task 1:** `tests/security/test_prompt_injection.py` — corpus of poisoned documents attempting: instruction override, tool invocation, cross-project data requests, system-prompt disclosure, citation forgery.
* **Task 2:** Assert the envelope holds and no tool call is emitted with non-user provenance.

### Phase 5 Exit Criteria
* Retrieved content is structurally delimited and prompt-declared as untrusted.
* Tool selection cannot be influenced by document or web content, enforced at the type level.
* The `exec()` fallback is gone.
* Adversarial suite passes in CI.

---

## Phase 6: Concurrency & Scale

**Problem:** [`conversations.py:271`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/api/v3/conversations.py) — `stream_message` is a sync `def` returning a sync generator, so Starlette runs the entire stream on an anyio worker thread while holding its `Session` for the stream's full duration. Ceiling ≈ 40 concurrent chats (default threadpool), each pinning a Postgres connection. Not urgent at current scale; it is the first thing to break under load, and it is structural.

### M15: SSE refactor
* **Task 1:** Convert `stream_message` to `async def` with an async generator; run blocking orchestrator steps via `asyncio.to_thread` / `run_in_threadpool` at the step granularity rather than holding a thread for the whole stream.
* **Task 2:** Scope DB sessions to individual operations instead of the stream lifetime. Persist assistant messages in short-lived sessions.
* **Task 3:** Configure connection-pool sizing explicitly (`pool_size`, `max_overflow`) against expected concurrency.
* **Task 4:** Add a load test (`tests/system/test_concurrent_streams.py`) establishing the real ceiling before and after.
* **Task 5:** Add client-disconnect handling so an abandoned stream releases resources and cancels in-flight LLM calls.

### Phase 6 Exit Criteria
* Concurrent stream capacity measurably exceeds the previous threadpool bound.
* DB connections are not held for stream duration.
* Disconnects free resources promptly.

---

## Phase 7: Eval Framework & CI Gating

**Rationale:** This is V4's Phase 4, deferred until now on purpose — the dataset from Phase 0 is the asset; the framework is packaging. With three phases of measured deltas behind it, adopting a framework is now worthwhile rather than premature.

### M16: DeepEval / Ragas adoption
* **Task 1:** Wrap the Phase 0 dataset in DeepEval test cases; add answer-quality metrics (faithfulness, answer relevancy, contextual precision/recall) on top of the existing retrieval metrics.
* **Task 2:** Extend the dataset with expected-answer and abstention assertions.
* **Task 3:** Add a `nightly-evals` GitHub Actions workflow (not per-PR — these cost money and are slow) that fails on regression against committed baselines.
* **Task 4:** Add a fast per-PR subset (~10 cases, cached embeddings) as a smoke gate.

### M17: Promptfoo red-teaming
* **Task 1:** `promptfooconfig.yaml` targeting the gate and synthesis models: injection, system disclosure, cross-project access.
* **Task 2:** Wire into the existing `security-tests` job in [`.github/workflows/ci.yml`](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/.github/workflows/ci.yml), which already runs Bandit and pip-audit.

### Phase 7 Exit Criteria
* Nightly evals gate on retrieval **and** answer quality against committed baselines.
* Red-team suite runs in CI alongside existing security checks.
* Every V5 phase has a recorded before/after in `backend/app/evals/results/`.

---

## Explicitly Deferred

| Item | Reason |
|---|---|
| **Graphiti** | Requires operating Neo4j to resolve temporal fact conflicts — a narrow slice of query volume. Revisit once retrieval is no longer the bottleneck. |
| **Letta** | Architecture mid-migration per its own repo. `memory_manager.py` already covers the current need. |
| **Microsoft Agent Framework** | Redundant — Burr already provides the state machine, checkpointing and inspectable control flow. |
| **Semantic answer cache** | Correctness risk (stale answers after reindex) outweighs the benefit until M10's hit-rate data justifies it. |

---

## Sequencing Summary

```
Phase 0  Golden dataset + metrics baseline        ← small, unblocks measurement
Phase 1  Prefetch widening → reranker             ← highest ROI
Phase 2  Docling → page-aware chunks → OCR        ← highest user-visible impact
Phase 3  Contextual headers → reindex
Phase 4  Cost accounting → dedup → cache → Qdrant
Phase 5  Injection hardening                      ← promote if tool surface grows
Phase 6  SSE concurrency                          ← promote on load-related incident
Phase 7  Eval framework + CI gating
```

Phases 1–3 are sequential (each measured against the prior). Phase 4 modules are independent and parallelizable. Phase 5 should be promoted ahead of Phase 4 if the agent's tool surface expands before then.
