-- Per-conversation document attachments for hybrid retrieval routing.

ALTER TABLE files
    ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES chat_conversations(id) ON DELETE CASCADE;

ALTER TABLE segments
    ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES chat_conversations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_files_conversation_id
    ON files(conversation_id)
    WHERE conversation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_segments_conversation_id
    ON segments(conversation_id)
    WHERE conversation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_files_conversation_status
    ON files(conversation_id, status)
    WHERE conversation_id IS NOT NULL;
