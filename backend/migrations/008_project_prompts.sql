-- Migration: Document project-level LLM prompt overrides
-- Since the `projects` table has a `settings` JSONB column, overrides can be dynamically stored.
-- This migration acts as a marker and ensures database connection is active.
SELECT 1;
