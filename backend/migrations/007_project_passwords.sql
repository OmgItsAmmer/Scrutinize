-- Migration: Add password_hash column to projects
ALTER TABLE projects ADD COLUMN IF NOT EXISTS password_hash TEXT;
