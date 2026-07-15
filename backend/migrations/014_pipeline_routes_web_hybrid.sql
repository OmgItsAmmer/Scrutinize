-- Migration 014: Allow web and hybrid routes in pipeline_runs.final_route
-- Required for Web Search → Always / hybrid pipeline logging (migration 003 only allowed generic|rag).

ALTER TABLE pipeline_runs DROP CONSTRAINT IF EXISTS pipeline_runs_final_route_check;

ALTER TABLE pipeline_runs ADD CONSTRAINT pipeline_runs_final_route_check
    CHECK (final_route IS NULL OR final_route IN ('generic', 'rag', 'web', 'hybrid'));
