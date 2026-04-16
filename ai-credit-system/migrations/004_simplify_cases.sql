-- Strip document data from cases — all document data now lives in the documents table.
ALTER TABLE cases DROP COLUMN IF EXISTS extracted_data;
ALTER TABLE cases DROP COLUMN IF EXISTS doc_types;
