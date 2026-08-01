-- V5 Phase 4 M8: Token & cost accounting columns.
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS prompt_tokens INT NULL;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS completion_tokens INT NULL;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS cached_tokens INT NULL;
ALTER TABLE pipeline_steps ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6) NULL;

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS total_cost_usd NUMERIC(10,6) NULL;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS total_tokens INT NULL;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_project_id ON pipeline_runs (project_id);
