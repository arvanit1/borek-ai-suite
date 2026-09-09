-- AT-61: retrievable in-app artifact metadata and integrity fields.

ALTER TABLE filed_artifacts ADD COLUMN IF NOT EXISTS file_name TEXT;
ALTER TABLE filed_artifacts ADD COLUMN IF NOT EXISTS size_bytes BIGINT;
ALTER TABLE filed_artifacts ADD COLUMN IF NOT EXISTS sha256 TEXT;
ALTER TABLE filed_artifacts ADD COLUMN IF NOT EXISTS journey_stage TEXT;
ALTER TABLE filed_artifacts ADD COLUMN IF NOT EXISTS storage_backend TEXT;
ALTER TABLE filed_artifacts
  ADD COLUMN IF NOT EXISTS prior_stage_presentation_version_id UUID
    REFERENCES presentation_versions(id) ON DELETE SET NULL;

ALTER TABLE filed_artifacts
  DROP CONSTRAINT IF EXISTS filed_artifacts_size_bytes_nonnegative;
ALTER TABLE filed_artifacts
  ADD CONSTRAINT filed_artifacts_size_bytes_nonnegative
    CHECK (size_bytes IS NULL OR size_bytes >= 0);

ALTER TABLE filed_artifacts
  DROP CONSTRAINT IF EXISTS filed_artifacts_sha256_format;
ALTER TABLE filed_artifacts
  ADD CONSTRAINT filed_artifacts_sha256_format
    CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$');

CREATE INDEX IF NOT EXISTS filed_artifacts_approved_at_idx
  ON filed_artifacts(approved_at DESC);
CREATE INDEX IF NOT EXISTS filed_artifacts_prior_stage_idx
  ON filed_artifacts(prior_stage_presentation_version_id);

DROP POLICY IF EXISTS "users_own_filed_artifacts" ON filed_artifacts;
DROP POLICY IF EXISTS "users_read_own_filed_artifacts" ON filed_artifacts;
CREATE POLICY "users_read_own_filed_artifacts"
  ON filed_artifacts
  FOR SELECT
  TO authenticated
  USING (
    opportunity_id IN (
      SELECT id FROM opportunities WHERE created_by = auth.uid()
    )
  );

CREATE OR REPLACE FUNCTION preserve_completed_filing()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD.status = 'filed' AND NEW.status <> 'filed' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS preserve_completed_filing_trigger ON filed_artifacts;
CREATE TRIGGER preserve_completed_filing_trigger
BEFORE UPDATE ON filed_artifacts
FOR EACH ROW EXECUTE FUNCTION preserve_completed_filing();
