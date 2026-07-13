CREATE TABLE IF NOT EXISTS chat_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (scope IN ('general', 'project')),
    retrieval_policy TEXT NOT NULL CHECK (retrieval_policy IN ('web_only', 'project_rag')),
    title VARCHAR(160) NOT NULL DEFAULT 'New chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    CHECK (
      (scope = 'general' AND project_id IS NULL AND retrieval_policy = 'web_only') OR
      (scope = 'project' AND project_id IS NOT NULL AND retrieval_policy = 'project_rag')
    )
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'streaming', 'completed', 'failed', 'cancelled')),
    client_message_id UUID,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE (conversation_id, client_message_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_owner_updated
    ON chat_conversations(owner_user_id, updated_at DESC) WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_chat_conversations_project_updated
    ON chat_conversations(project_id, updated_at DESC) WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
    ON chat_messages(conversation_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_files_project_uploaded ON files(project_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_project_status ON files(project_id, status);
CREATE INDEX IF NOT EXISTS idx_segments_project_file ON segments(project_id, file_id);
