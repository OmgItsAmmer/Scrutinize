-- Migration: 015_tool_approvals.sql
-- Create tool approvals table for human-in-the-loop validation gates.

CREATE TABLE IF NOT EXISTS tool_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,
    tool_name VARCHAR(255) NOT NULL,
    arguments JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'waiting', -- waiting, approved, rejected
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_approvals_conversation_id ON tool_approvals(conversation_id);
