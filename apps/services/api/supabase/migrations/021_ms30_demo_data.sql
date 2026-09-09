-- MS-30 + AT-61 lineage freeze: owner-scoped demo fixtures and stage lineage.

ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE opportunity_client_logos ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE framework_versions ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE presentation_plans ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE presentation_versions ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE slides ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE filed_artifacts ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE knowledge_corpus_versions ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS demo_marker TEXT;
ALTER TABLE knowledge_facts ADD COLUMN IF NOT EXISTS demo_marker TEXT;

ALTER TABLE presentation_versions
  ADD COLUMN IF NOT EXISTS journey_stage TEXT;
ALTER TABLE presentation_versions
  ADD COLUMN IF NOT EXISTS prior_stage_presentation_version_id UUID
    REFERENCES presentation_versions(id) ON DELETE SET NULL;

ALTER TABLE knowledge_corpus_versions
  ADD COLUMN IF NOT EXISTS owner_user_id UUID;

ALTER TABLE knowledge_corpus_versions
  DROP CONSTRAINT IF EXISTS knowledge_corpus_versions_corpus_key_version_key;
CREATE UNIQUE INDEX IF NOT EXISTS knowledge_corpus_versions_identity_idx
  ON knowledge_corpus_versions(
    corpus_key,
    version,
    COALESCE(owner_user_id, '00000000-0000-0000-0000-000000000000'::uuid)
  );

ALTER TABLE presentation_versions
  DROP CONSTRAINT IF EXISTS presentation_versions_journey_stage_check;
ALTER TABLE presentation_versions
  ADD CONSTRAINT presentation_versions_journey_stage_check
    CHECK (
      journey_stage IS NULL
      OR journey_stage IN ('first_contact', 'deepening', 'concretisation')
    );

CREATE INDEX IF NOT EXISTS presentation_versions_prior_stage_idx
  ON presentation_versions(prior_stage_presentation_version_id);
CREATE INDEX IF NOT EXISTS knowledge_corpus_versions_owner_idx
  ON knowledge_corpus_versions(owner_user_id, corpus_key, version);

DROP POLICY IF EXISTS "authenticated_read_approved_corpus_versions"
  ON knowledge_corpus_versions;
CREATE POLICY "authenticated_read_approved_corpus_versions"
  ON knowledge_corpus_versions
  FOR SELECT
  TO authenticated
  USING (
    status = 'approved'
    AND (owner_user_id IS NULL OR owner_user_id = auth.uid())
  );

DROP POLICY IF EXISTS "authenticated_read_approved_knowledge_documents"
  ON knowledge_documents;
CREATE POLICY "authenticated_read_approved_knowledge_documents"
  ON knowledge_documents
  FOR SELECT
  TO authenticated
  USING (
    classification IN ('public', 'internal')
    AND corpus_version_id IN (
      SELECT id FROM knowledge_corpus_versions
      WHERE status = 'approved'
        AND (owner_user_id IS NULL OR owner_user_id = auth.uid())
    )
  );

DROP POLICY IF EXISTS "authenticated_read_approved_knowledge_facts"
  ON knowledge_facts;
CREATE POLICY "authenticated_read_approved_knowledge_facts"
  ON knowledge_facts
  FOR SELECT
  TO authenticated
  USING (
    document_id IN (
      SELECT d.id
      FROM knowledge_documents d
      INNER JOIN knowledge_corpus_versions c ON c.id = d.corpus_version_id
      WHERE c.status = 'approved'
        AND d.classification IN ('public', 'internal')
        AND (c.owner_user_id IS NULL OR c.owner_user_id = auth.uid())
    )
  );
