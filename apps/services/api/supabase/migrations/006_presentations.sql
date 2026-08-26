-- AT-37 migration 006: presentations (v2 §23)

CREATE TABLE IF NOT EXISTS presentations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_plan_id UUID NOT NULL
    REFERENCES presentation_plans(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE presentations ENABLE ROW LEVEL SECURITY;
