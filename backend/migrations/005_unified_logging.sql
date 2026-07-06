-- Migration 005: Unified pipeline logging schema (idempotent)
-- Canonical shape: docs/db/schema.md
-- Safe to re-run — does NOT drop existing pipeline_runs / pipeline_steps.

-- Remove legacy polymorphic tables from 003/004 if still present
DROP TABLE IF EXISTS retrieved_sources CASCADE;
DROP TABLE IF EXISTS step_retrievals CASCADE;
DROP TABLE IF EXISTS step_rewrites CASCADE;
DROP TABLE IF EXISTS step_gates CASCADE;
DROP TABLE IF EXISTS step_syntheses CASCADE;
DROP TABLE IF EXISTS step_evaluations CASCADE;

-- Remove interim 004 column (not in canonical schema)
ALTER TABLE pipeline_steps DROP COLUMN IF EXISTS details;

-- ---------------------------------------------------------------------------
-- pipeline_runs
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

-- 003 used "query" instead of "original_query"
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

UPDATE pipeline_runs SET original_query = '' WHERE original_query IS NULL;
UPDATE pipeline_runs SET attempts_count = 0 WHERE attempts_count IS NULL;
UPDATE pipeline_runs SET disclaimer_appended = FALSE WHERE disclaimer_appended IS NULL;
UPDATE pipeline_runs SET run_metadata = '{}'::jsonb WHERE run_metadata IS NULL;
UPDATE pipeline_runs SET created_at = NOW() WHERE created_at IS NULL;
UPDATE pipeline_runs SET start_time = NOW() WHERE start_time IS NULL;

-- ---------------------------------------------------------------------------
-- pipeline_steps
-- ---------------------------------------------------------------------------
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

ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS model_name TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS model_input JSONB;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS raw_thinking TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS model_output TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS structured_output JSONB;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS retrieved_sources JSONB;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

-- ---------------------------------------------------------------------------
-- Indexes (base set)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run_id ON pipeline_steps (run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_step_type ON pipeline_steps (step_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_attempt ON pipeline_steps (attempt);
