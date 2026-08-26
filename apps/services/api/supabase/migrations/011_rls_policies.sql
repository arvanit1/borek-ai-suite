-- AT-38 migration 011: Row Level Security policies (v2 §23 / §26)

DROP POLICY IF EXISTS "users_own_opportunities" ON opportunities;
CREATE POLICY "users_own_opportunities"
  ON opportunities
  FOR ALL
  USING (created_by = auth.uid());

DROP POLICY IF EXISTS "users_own_transcripts" ON transcripts;
CREATE POLICY "users_own_transcripts"
  ON transcripts
  FOR ALL
  USING (
    opportunity_id IN (
      SELECT id FROM opportunities
      WHERE created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_transcript_sections" ON transcript_sections;
CREATE POLICY "users_own_transcript_sections"
  ON transcript_sections
  FOR ALL
  USING (
    transcript_id IN (
      SELECT t.id
      FROM transcripts t
      INNER JOIN opportunities o ON o.id = t.opportunity_id
      WHERE o.created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_framework_versions" ON framework_versions;
CREATE POLICY "users_own_framework_versions"
  ON framework_versions
  FOR ALL
  USING (
    opportunity_id IN (
      SELECT id FROM opportunities
      WHERE created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_presentation_plans" ON presentation_plans;
CREATE POLICY "users_own_presentation_plans"
  ON presentation_plans
  FOR ALL
  USING (
    framework_version_id IN (
      SELECT fv.id
      FROM framework_versions fv
      INNER JOIN opportunities o ON o.id = fv.opportunity_id
      WHERE o.created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_presentations" ON presentations;
CREATE POLICY "users_own_presentations"
  ON presentations
  FOR ALL
  USING (
    presentation_plan_id IN (
      SELECT pp.id
      FROM presentation_plans pp
      INNER JOIN framework_versions fv ON fv.id = pp.framework_version_id
      INNER JOIN opportunities o ON o.id = fv.opportunity_id
      WHERE o.created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_presentation_versions" ON presentation_versions;
CREATE POLICY "users_own_presentation_versions"
  ON presentation_versions
  FOR ALL
  USING (
    presentation_id IN (
      SELECT p.id
      FROM presentations p
      INNER JOIN presentation_plans pp ON pp.id = p.presentation_plan_id
      INNER JOIN framework_versions fv ON fv.id = pp.framework_version_id
      INNER JOIN opportunities o ON o.id = fv.opportunity_id
      WHERE o.created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_slides" ON slides;
CREATE POLICY "users_own_slides"
  ON slides
  FOR ALL
  USING (
    presentation_version_id IN (
      SELECT pv.id
      FROM presentation_versions pv
      INNER JOIN presentations p ON p.id = pv.presentation_id
      INNER JOIN presentation_plans pp ON pp.id = p.presentation_plan_id
      INNER JOIN framework_versions fv ON fv.id = pp.framework_version_id
      INNER JOIN opportunities o ON o.id = fv.opportunity_id
      WHERE o.created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_generation_jobs" ON generation_jobs;
CREATE POLICY "users_own_generation_jobs"
  ON generation_jobs
  FOR ALL
  USING (
    opportunity_id IN (
      SELECT id FROM opportunities
      WHERE created_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS "users_own_audit_entries" ON audit_log;
CREATE POLICY "users_own_audit_entries"
  ON audit_log
  FOR ALL
  USING (actor_id = auth.uid());
