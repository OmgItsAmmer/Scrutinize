-- Scrutinize relational schema (Neon Postgres)
-- Mirrors docs/architecture/architecture.md section 8
-- Apply with: make db-migrate
-- SQLModel also calls create_all() on backend startup for dev parity

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    modality TEXT NOT NULL CHECK (modality IN ('text', 'audio', 'video')),
    storage_path TEXT NOT NULL,
    duration_seconds NUMERIC,
    size_bytes BIGINT,
    status TEXT NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'processing', 'indexed', 'failed')),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'done', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    modality TEXT NOT NULL,
    content TEXT NOT NULL,
    start_time NUMERIC,
    end_time NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_segments_file_id ON segments (file_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_file_id_status ON processing_jobs (file_id, status);
