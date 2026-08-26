-- AT-37 migration 007: presentation_versions (v2 §23)

CREATE TABLE IF NOT EXISTS presentation_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_id UUID NOT NULL
    REFERENCES presentations(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL DEFAULT 1,
  slides_json JSONB NOT NULL,
  pptx_storage_path TEXT,
  pdf_storage_path TEXT,
  status TEXT NOT NULL DEFAULT 'generating',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE presentation_versions ENABLE ROW LEVEL SECURITY;
