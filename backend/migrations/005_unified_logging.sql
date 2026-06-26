-- Migration 005: Unified Pipeline Logging Schema

-- Drop older polymorphic logging tables if they exist
DROP TABLE IF EXISTS step_rewrites CASCADE;
DROP TABLE IF EXISTS step_gates CASCADE;
DROP TABLE IF EXISTS step_retrievals CASCADE;
DROP TABLE IF EXISTS retrieved_sources CASCADE;
DROP TABLE IF EXISTS step_syntheses CASCADE;
DROP TABLE IF EXISTS step_evaluations CASCADE;
DROP TABLE IF EXISTS pipeline_steps CASCADE;
DROP TABLE IF EXISTS pipeline_runs CASCADE;

-- Recreate pipeline_runs table with unified run-level columns
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_query TEXT NOT NULL,
    modality_filter TEXT CHECK (modality_filter IN ('text', 'audio', 'video')),
    conversation_context TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    final_route TEXT CHECK (final_route IN ('generic', 'rag')),
    final_answer TEXT,
    final_confidence NUMERIC,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    disclaimer_appended BOOLEAN NOT NULL DEFAULT FALSE,
    run_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Recreate pipeline_steps table with unified step/LLM log columns
CREATE TABLE pipeline_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_type TEXT NOT NULL CHECK (step_type IN ('rewrite', 'gate', 'retrieval', 'synthesis', 'evaluation')),
    attempt INTEGER NOT NULL,
    model_name TEXT,
    model_input JSONB,
    raw_thinking TEXT,
    model_output TEXT,
    structured_output JSONB,
    retrieved_sources JSONB,
    latency_ms INTEGER,
    status TEXT CHECK (status IN ('success', 'failure')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX idx_pipeline_steps_run_id ON pipeline_steps (run_id);
CREATE INDEX idx_pipeline_steps_step_type ON pipeline_steps (step_type);
CREATE INDEX idx_pipeline_steps_attempt ON pipeline_steps (attempt);
