-- AT-61: durable, idempotent enterprise artifact filing metadata.
-- File bytes remain in the approved enterprise repository; this table owns
-- workflow, provenance, approval, audit, and retry state.

CREATE TABLE IF NOT EXISTS filed_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key TEXT NOT NULL UNIQUE,
  opportunity_id UUID NOT NULL
    REFERENCES opportunities(id) ON DELETE CASCADE,
  presentation_id UUID NOT NULL
    REFERENCES presentations(id) ON DELETE CASCADE,
  presentation_version_id UUID NOT NULL
    REFERENCES presentation_versions(id) ON DELETE CASCADE,
  framework_version_id UUID NOT NULL
    REFERENCES framework_versions(id) ON DELETE RESTRICT,
  artifact_kind TEXT NOT NULL,
  content_type TEXT NOT NULL,
  provider TEXT NOT NULL,
  destination_path TEXT NOT NULL,
  repository_ref TEXT,
  status TEXT NOT NULL DEFAULT 'filing'
    CHECK (status IN ('filing', 'filed', 'failed')),
  approved_by UUID NOT NULL,
  approved_at TIMESTAMPTZ NOT NULL,
  corpus_versions JSONB NOT NULL DEFAULT '[]'::jsonb,
  error_code TEXT,
  error_retryable BOOLEAN,
  filed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS filed_artifacts_opportunity_idx
  ON filed_artifacts(opportunity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS filed_artifacts_presentation_version_idx
  ON filed_artifacts(presentation_version_id);

ALTER TABLE filed_artifacts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_own_filed_artifacts" ON filed_artifacts;
CREATE POLICY "users_own_filed_artifacts"
  ON filed_artifacts
  FOR ALL
  USING (
    opportunity_id IN (
      SELECT id FROM opportunities
      WHERE created_by = auth.uid()
    )
  )
  WITH CHECK (
    opportunity_id IN (
      SELECT id FROM opportunities
      WHERE created_by = auth.uid()
    )
  );
