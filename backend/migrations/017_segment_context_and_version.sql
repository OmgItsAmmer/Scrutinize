-- V5 Phase 3 M6/M7: contextual retrieval header + pipeline generation tracking.
ALTER TABLE segments ADD COLUMN IF NOT EXISTS context_header TEXT NULL;
ALTER TABLE segments ADD COLUMN IF NOT EXISTS pipeline_version INT NOT NULL DEFAULT 1;
