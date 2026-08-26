-- AT-37 migration 003: transcript_sections (v2 §23)

CREATE TABLE IF NOT EXISTS transcript_sections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transcript_id UUID NOT NULL
    REFERENCES transcripts(id) ON DELETE CASCADE,
  section_index INTEGER NOT NULL,
  speaker_role TEXT,
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'
);

ALTER TABLE transcript_sections ENABLE ROW LEVEL SECURITY;
