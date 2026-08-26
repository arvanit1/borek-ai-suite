-- AT-37 migration 010: audit_log (v2 §23)

CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id UUID NOT NULL,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id UUID NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
