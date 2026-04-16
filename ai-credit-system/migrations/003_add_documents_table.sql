-- Each uploaded file gets its own row, linked to a case.
CREATE TABLE IF NOT EXISTS documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id      UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    document_name TEXT NOT NULL,
    doc_type     TEXT,
    metadata     JSONB DEFAULT '{}',
    extracted_data JSONB DEFAULT '{}',
    status       TEXT DEFAULT 'pending',
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_case_id   ON documents(case_id);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type  ON documents(doc_type);
