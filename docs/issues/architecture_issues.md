# Architecture Issues

## Quality Issue
- The `Generic` path forces a full evaluation by the `DecisionAgent` after synthesis. If the gate successfully answers directly, evaluating that fixed response wastes time and may yield false negatives.
- Out-of-context queries (e.g., "how to play fifa") can still enter the expensive RAG pipeline when the gate misclassifies or when `DecisionAgent` escalates generic → RAG. **Fixed (partial):** removed `is_contextual_follow_up` heuristic; gate now receives the full conversation snapshot with UTC timestamps and classifies before any rewrite. Gate JSON parse failures now default to `generic` instead of `rag`.
- No retrieval relevance floor: once on the RAG path, `RrfRetriever` always returns top-k chunks regardless of similarity score.

## Resource Issue
- High latency and compute cost due to long sequential LLM chains. A successful RAG request requires up to 4 LLM calls (`gate` → `rewrite` → `synthesis` → `evaluate`), and up to 7 on retries.
- Escalating from `Generic` to `RAG` path means throwing away the time spent generating and evaluating the generic response.

## Quality Suggestion
- Provide more direct fallback paths instead of strictly needing the `DecisionAgent` to evaluate every single path, especially simple generic responses.

## Resource Suggestion
- Implement a semantic caching layer (e.g., caching identical rewritten queries and their Qdrant results or final answers) to avoid hitting the LLMs repeatedly for common queries.
- Run the `GenericAgent` synthesis and `DecisionAgent` generic evaluation concurrently if possible, or bypass the `DecisionAgent` for direct gate replies.

## Proposed Fixes

### 1. Wasted Evaluation on Direct Gate Replies
**Fix:** Modify `_handle_generic_path` in `pipeline_orchestrator.py` so that if `gate_result.reply` is populated, the pipeline bypasses the `DecisionAgent` entirely. It should simply log the synthesis and return the final response, saving 1 full LLM evaluation cycle.

### 2. Wasted Compute on Escalate-to-RAG
**Fix:** If escalation from `Generic` to `RAG` does happen, pass the already-generated generic draft to the `RagSynthesisAgent` as a fallback context, ensuring the compute isn't completely discarded. Guard escalation so clearly off-topic queries cannot be forced into RAG.

### 3. Lack of Caching
**Fix:** Integrate a caching layer (e.g., Redis or an in-memory LRU cache). Store the final `SearchV2Response` indexed by the `rewritten_query`. Before entering the RAG or Generic branches, check the cache for an exact match and return it instantly to bypass embedding and LLM generation.

### 4. No Retrieval Relevance Floor
**Fix:** Add a minimum similarity score threshold in `RrfRetriever` or `_run_rag_pipeline`. When all chunk scores are below the threshold, short-circuit to a generic "not in your library" response instead of synthesizing from weak matches.

## Resolved

### Gate-first routing with full conversation context
**Was:** `is_contextual_follow_up()` heuristic filtered conversation history before gate/rewrite. `QueryRewriter` ran before `RagGate`, biasing off-topic queries toward retrieval. Gate and RAG path used inconsistent context scoping.

**Now:** `RagGate` runs first with the current query and full conversation snapshot (UTC timestamps). Generic path answers via gate or `GenericAgent`, then `DecisionAgent` evaluates with original query + context. `QueryRewriter` runs only as the first step inside the RAG path.
