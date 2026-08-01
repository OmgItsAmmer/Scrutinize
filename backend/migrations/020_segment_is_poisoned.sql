-- V5 Phase 5 M12: Flag poisoned segments.
ALTER TABLE segments ADD COLUMN IF NOT EXISTS is_poisoned BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_segments_is_poisoned ON segments (is_poisoned);
