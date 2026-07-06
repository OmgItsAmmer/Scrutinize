-- Migration 009: Pipeline logging v2 — retrieval debug indexes (idempotent)
--
-- Target schema: docs/db/schema.md
-- Base tables/columns are created by 005_unified_logging.sql.
--
-- Retrieval hybrid-search metrics are stored in JSONB (no extra columns):
--   pipeline_steps.structured_output -> 'retrieval'
--     semantic_prefetch_count, keyword_prefetch_count, qdrant_retrieved_count,
--     sparse_query_dimensions, rrf.{k,fused_count,semantic_only,keyword_only,both_lists}
--   pipeline_steps.retrieved_sources[] per chunk:
--     semantic_rank, keyword_rank, in_semantic_list, in_keyword_list, score, rank
--
-- Apply: make scrutinize-migrate

-- ---------------------------------------------------------------------------
-- 1. Ensure legacy tables from 003/004 are gone
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS retrieved_sources CASCADE;
DROP TABLE IF EXISTS step_retrievals CASCADE;
DROP TABLE IF EXISTS step_rewrites CASCADE;
DROP TABLE IF EXISTS step_gates CASCADE;
DROP TABLE IF EXISTS step_syntheses CASCADE;
DROP TABLE IF EXISTS step_evaluations CASCADE;

ALTER TABLE pipeline_steps DROP COLUMN IF EXISTS details;

-- ---------------------------------------------------------------------------
-- 2. Ensure core logging tables match docs/db/schema.md (additive only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_query TEXT NOT NULL,
    modality_filter TEXT,
    conversation_context TEXT,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    final_route TEXT,
    final_answer TEXT,
    final_confidence NUMERIC,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    disclaimer_appended BOOLEAN NOT NULL DEFAULT FALSE,
    run_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_type TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    model_name TEXT,
    model_input JSONB,
    raw_thinking TEXT,
    model_output TEXT,
    structured_output JSONB,
    retrieved_sources JSONB,
    latency_ms INTEGER,
    status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'pipeline_runs'
          AND column_name = 'query'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'pipeline_runs'
          AND column_name = 'original_query'
    ) THEN
        ALTER TABLE pipeline_runs RENAME COLUMN query TO original_query;
    END IF;
END $$;

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS original_query TEXT;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS modality_filter TEXT;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS conversation_context TEXT;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS final_route TEXT;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS final_answer TEXT;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS final_confidence NUMERIC;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS attempts_count INTEGER DEFAULT 0;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS disclaimer_appended BOOLEAN DEFAULT FALSE;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS run_metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS model_name TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS model_input JSONB;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS raw_thinking TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS model_output TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS structured_output JSONB;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS retrieved_sources JSONB;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

UPDATE pipeline_runs SET original_query = '' WHERE original_query IS NULL;
UPDATE pipeline_runs SET attempts_count = 0 WHERE attempts_count IS NULL;
UPDATE pipeline_runs SET disclaimer_appended = FALSE WHERE disclaimer_appended IS NULL;
UPDATE pipeline_runs SET run_metadata = '{}'::jsonb WHERE run_metadata IS NULL;
UPDATE pipeline_runs SET created_at = NOW() WHERE created_at IS NULL;
UPDATE pipeline_runs SET start_time = NOW() WHERE start_time IS NULL;

UPDATE pipeline_steps SET created_at = NOW() WHERE created_at IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Indexes for trace + hybrid retrieval debugging (logging.md queries)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run_id ON pipeline_steps (run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_step_type ON pipeline_steps (step_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_attempt ON pipeline_steps (attempt);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_created_at ON pipeline_steps (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_steps_retrieval
    ON pipeline_steps (created_at DESC)
    WHERE step_type = 'retrieval';

-- GIN indexes: only when columns exist and are jsonb (avoids errors on partial schemas)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'pipeline_steps'
          AND column_name = 'structured_output'
          AND udt_name = 'jsonb'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'idx_pipeline_steps_structured_output_gin'
    ) THEN
        CREATE INDEX idx_pipeline_steps_structured_output_gin
            ON pipeline_steps USING GIN (structured_output jsonb_path_ops);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'pipeline_steps'
          AND column_name = 'retrieved_sources'
          AND udt_name = 'jsonb'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'idx_pipeline_steps_retrieved_sources_gin'
    ) THEN
        CREATE INDEX idx_pipeline_steps_retrieved_sources_gin
            ON pipeline_steps USING GIN (retrieved_sources jsonb_path_ops);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 4. Documentation comments
-- ---------------------------------------------------------------------------
COMMENT ON TABLE pipeline_runs IS 'v2 pipeline execution log — one row per user search (see docs/db/schema.md)';
COMMENT ON TABLE pipeline_steps IS 'v2 pipeline step trace — gate, rewrite, retrieval, synthesis, evaluation';
COMMENT ON COLUMN pipeline_runs.run_metadata IS 'Extensible run-level JSON (pipeline config snapshot, etc.)';
COMMENT ON COLUMN pipeline_steps.structured_output IS 'Parsed step output; retrieval steps include key retrieval with hybrid search counts';
COMMENT ON COLUMN pipeline_steps.retrieved_sources IS 'JSON array of chunk snapshots with semantic_rank, keyword_rank, score, rank';
