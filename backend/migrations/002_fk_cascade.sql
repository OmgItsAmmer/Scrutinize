-- Ensure child rows cascade when a file is deleted.
-- Needed when tables were created via SQLModel create_all() (no ON DELETE CASCADE).

ALTER TABLE processing_jobs
  DROP CONSTRAINT IF EXISTS processing_jobs_file_id_fkey;

ALTER TABLE processing_jobs
  ADD CONSTRAINT processing_jobs_file_id_fkey
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE;

ALTER TABLE segments
  DROP CONSTRAINT IF EXISTS segments_file_id_fkey;

ALTER TABLE segments
  ADD CONSTRAINT segments_file_id_fkey
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE;
