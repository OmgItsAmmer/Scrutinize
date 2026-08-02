-- Dev debug sidebar: persist the full pre-rerank RRF candidate pool (up to
-- rerank_candidate_pool, e.g. 50) alongside the existing final top-k retrieved_sources,
-- so the debug UI can show/filter the full semantic+keyword candidate set per query.
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS retrieval_candidates JSONB NULL;

CREATE INDEX IF NOT EXISTS idx_pipeline_steps_retrieval_candidates_gin
    ON pipeline_steps USING gin (retrieval_candidates jsonb_path_ops);
