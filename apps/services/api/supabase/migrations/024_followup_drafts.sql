-- BT-33: follow-up draft persistence and draft→sent learning log.

CREATE TABLE IF NOT EXISTS followup_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL
    REFERENCES opportunities(id) ON DELETE CASCADE,
  job_id UUID NOT NULL
    REFERENCES generation_jobs(id) ON DELETE CASCADE,
  meeting_owner_id UUID NOT NULL,
  project_key TEXT NOT NULL,
  extraction_json JSONB NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  review_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  attachment_name TEXT,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'reviewed', 'sent', 'sent_unknown')),
  provider_draft_id TEXT,
  idempotency_key TEXT NOT NULL UNIQUE,
  reviewed_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS followup_drafts_opportunity_idx
  ON followup_drafts(opportunity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS followup_sent_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL
    REFERENCES opportunities(id) ON DELETE CASCADE,
  followup_draft_id UUID NOT NULL
    REFERENCES followup_drafts(id) ON DELETE CASCADE,
  meeting_owner_id UUID NOT NULL,
  generated_subject TEXT NOT NULL,
  generated_body TEXT NOT NULL,
  final_subject TEXT,
  final_body TEXT,
  delivery_status TEXT NOT NULL
    CHECK (delivery_status IN ('sent', 'sent_unknown')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS followup_sent_log_opportunity_idx
  ON followup_sent_log(opportunity_id, created_at DESC);

ALTER TABLE followup_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE followup_sent_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_own_followup_drafts" ON followup_drafts;
CREATE POLICY "users_own_followup_drafts"
  ON followup_drafts
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

DROP POLICY IF EXISTS "users_own_followup_sent_log" ON followup_sent_log;
CREATE POLICY "users_own_followup_sent_log"
  ON followup_sent_log
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
