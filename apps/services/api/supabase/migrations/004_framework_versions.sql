-- AT-37 migration 004: framework_versions (v2 §23)

CREATE TABLE IF NOT EXISTS framework_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL
    REFERENCES opportunities(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'draft',
  framework_json JSONB NOT NULL,
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE framework_versions ENABLE ROW LEVEL SECURITY;
