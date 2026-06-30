-- Migration: Plug-and-play multi-tenant support
-- ADR: docs/decisions/001_ADR_plug_and_play.md
-- Apply with: make db-migrate

-- 1. Create the projects table with dual API key strategy (admin + client).
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    -- Private admin key (scrutinize_sk_...): upload/management operations only.
    api_key TEXT NOT NULL UNIQUE,
    -- Public client key (scrutinize_pk_...): read-only search/chat endpoints.
    client_key TEXT NOT NULL UNIQUE,
    -- CORS allowlist for client_key embedding, e.g. '["https://myapp.com"]'.
    allowed_origins JSONB NOT NULL DEFAULT '[]',
    -- Per-project pipeline overrides (models, thresholds, system prompts).
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_api_key ON projects (api_key);
CREATE INDEX IF NOT EXISTS idx_projects_client_key ON projects (client_key);

-- 2. Insert a "legacy" default project to backfill existing rows.
--    This project has no usable keys (backfill only — obtain real keys via POST /api/v2/projects).
INSERT INTO projects (id, name, api_key, client_key, settings)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    '__legacy__',
    'scrutinize_sk_legacy_backfill_only',
    'scrutinize_pk_legacy_backfill_only',
    '{}'
)
ON CONFLICT (name) DO NOTHING;

-- 3. Add project_id FK to files (nullable — existing rows backfill to legacy project).
ALTER TABLE files
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

UPDATE files
SET project_id = '00000000-0000-0000-0000-000000000001'
WHERE project_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_files_project_id ON files (project_id);

-- 4. Add project_id FK to segments (denormalized for fast per-project queries).
ALTER TABLE segments
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

UPDATE segments s
SET project_id = f.project_id
FROM files f
WHERE s.file_id = f.id AND s.project_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_segments_project_id ON segments (project_id);
