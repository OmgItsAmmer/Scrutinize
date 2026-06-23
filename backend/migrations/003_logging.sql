-- Migration 003: Pipeline Logging Schema

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    modality_filter TEXT CHECK (modality_filter IN ('text', 'audio', 'video')),
    conversation_context TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    final_route TEXT CHECK (final_route IN ('generic', 'rag')),
    final_answer TEXT,
    final_confidence NUMERIC,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    disclaimer_appended BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_type TEXT NOT NULL CHECK (step_type IN ('rewrite', 'gate', 'retrieval', 'synthesis', 'evaluation')),
    attempt INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS step_rewrites (
    step_id UUID PRIMARY KEY REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    input_query TEXT NOT NULL,
    prev_feedback TEXT,
    rewritten_query TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS step_gates (
    step_id UUID PRIMARY KEY REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    route TEXT NOT NULL CHECK (route IN ('generic', 'rag')),
    reason TEXT,
    reply TEXT
);

CREATE TABLE IF NOT EXISTS step_retrievals (
    step_id UUID PRIMARY KEY REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    rewritten_query TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retrieved_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id UUID NOT NULL REFERENCES step_retrievals(step_id) ON DELETE CASCADE,
    segment_id UUID REFERENCES segments(id) ON DELETE SET NULL,
    file_id UUID REFERENCES files(id) ON DELETE SET NULL,
    modality TEXT NOT NULL CHECK (modality IN ('text', 'audio', 'video')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_path TEXT NOT NULL,
    start_time NUMERIC,
    end_time NUMERIC,
    score NUMERIC NOT NULL,
    rank INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS step_syntheses (
    step_id UUID PRIMARY KEY REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS step_evaluations (
    step_id UUID PRIMARY KEY REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK (verdict IN ('good', 'bad')),
    confidence NUMERIC NOT NULL,
    correct_route TEXT CHECK (correct_route IN ('generic', 'rag')),
    feedback TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run_id ON pipeline_steps (run_id);
CREATE INDEX IF NOT EXISTS idx_retrieved_sources_step_id ON retrieved_sources (step_id);
CREATE INDEX IF NOT EXISTS idx_retrieved_sources_segment_id ON retrieved_sources (segment_id);
CREATE INDEX IF NOT EXISTS idx_retrieved_sources_file_id ON retrieved_sources (file_id);
