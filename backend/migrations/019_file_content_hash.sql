-- V5 Phase 4 M9: Content-hash deduplication column and indexes.
ALTER TABLE files ADD COLUMN IF NOT EXISTS content_sha256 TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_files_content_sha256 ON files (content_sha256);
CREATE UNIQUE INDEX IF NOT EXISTS idx_files_project_content_sha256 ON files (project_id, content_sha256) WHERE content_sha256 IS NOT NULL;
