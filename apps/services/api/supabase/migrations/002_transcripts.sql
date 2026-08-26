-- AT-37 migration 002: transcripts (v2 §23)

CREATE TABLE IF NOT EXISTS transcripts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL
    REFERENCES opportunities(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  processing_status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
