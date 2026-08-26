-- AT-37 migration 005: presentation_plans (v2 §23)

CREATE TABLE IF NOT EXISTS presentation_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  framework_version_id UUID NOT NULL
    REFERENCES framework_versions(id) ON DELETE CASCADE,
  plan_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE presentation_plans ENABLE ROW LEVEL SECURITY;
