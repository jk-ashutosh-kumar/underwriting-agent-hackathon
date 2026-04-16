-- Add doc_types array to cases to track which document types have been ingested
ALTER TABLE cases ADD COLUMN IF NOT EXISTS doc_types TEXT[] DEFAULT '{}';
