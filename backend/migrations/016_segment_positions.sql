-- V5 M4: page-aware segments — position metadata for citations and structure-aware chunking.
ALTER TABLE segments ADD COLUMN IF NOT EXISTS page_number INT NULL;
ALTER TABLE segments ADD COLUMN IF NOT EXISTS section_path TEXT NULL;
ALTER TABLE segments ADD COLUMN IF NOT EXISTS char_start INT NULL;
ALTER TABLE segments ADD COLUMN IF NOT EXISTS char_end INT NULL;
ALTER TABLE segments ADD COLUMN IF NOT EXISTS block_type TEXT NULL;
