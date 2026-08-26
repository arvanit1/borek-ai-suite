-- AT-37 migration 008: slides (v2 §23)

CREATE TABLE IF NOT EXISTS slides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_version_id UUID NOT NULL
    REFERENCES presentation_versions(id) ON DELETE CASCADE,
  slide_index INTEGER NOT NULL,
  layout_id TEXT NOT NULL,
  slide_spec JSONB NOT NULL,
  source_chapter_ids TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE slides ENABLE ROW LEVEL SECURITY;
