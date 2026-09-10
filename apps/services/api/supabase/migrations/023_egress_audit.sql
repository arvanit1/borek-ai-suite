-- BT-32: durable per-send egress decisions. Metadata only — never payload bodies.

CREATE TABLE IF NOT EXISTS egress_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL REFERENCES opportunities(id)
    ON DELETE CASCADE,
  presentation_version_id UUID NOT NULL REFERENCES presentation_versions(id)
    ON DELETE CASCADE,
  journey_stage TEXT NOT NULL,
  provider TEXT NOT NULL,
  pipeline_stage TEXT NOT NULL,
  decision TEXT NOT NULL,
  fields JSONB NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT egress_audit_decision_allowed_or_blocked
    CHECK (decision IN ('allowed', 'blocked')),
  CONSTRAINT egress_audit_attempt_positive
    CHECK (attempt >= 1)
);

ALTER TABLE egress_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_own_egress_audit" ON egress_audit;
CREATE POLICY "users_own_egress_audit"
  ON egress_audit FOR ALL
  USING (
    opportunity_id IN (
      SELECT id FROM opportunities
      WHERE created_by = auth.uid()
    )
  );

CREATE INDEX IF NOT EXISTS egress_audit_opportunity_idx
  ON egress_audit(opportunity_id);

CREATE INDEX IF NOT EXISTS egress_audit_version_stage_idx
  ON egress_audit(presentation_version_id, journey_stage, created_at);
