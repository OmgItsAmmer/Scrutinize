-- Migration 004: Simplify Pipeline Logging Schema
-- Replaces polymorphic step tables with a JSONB details column.

-- 1. Add JSONB details column to pipeline_steps
ALTER TABLE pipeline_steps
ADD COLUMN details JSONB DEFAULT '{}'::jsonb;

-- 2. Update retrieved_sources to point to pipeline_steps instead of step_retrievals
ALTER TABLE retrieved_sources
DROP CONSTRAINT IF EXISTS retrieved_sources_step_id_fkey;

ALTER TABLE retrieved_sources
ADD CONSTRAINT retrieved_sources_step_id_fkey 
FOREIGN KEY (step_id) REFERENCES pipeline_steps(id) ON DELETE CASCADE;

-- 3. Drop the specific step tables
DROP TABLE IF EXISTS step_rewrites CASCADE;
DROP TABLE IF EXISTS step_gates CASCADE;
DROP TABLE IF EXISTS step_retrievals CASCADE;
DROP TABLE IF EXISTS step_syntheses CASCADE;
DROP TABLE IF EXISTS step_evaluations CASCADE;

-- 4. Create a GIN index on the details JSONB column for efficient querying
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_details ON pipeline_steps USING GIN (details);
