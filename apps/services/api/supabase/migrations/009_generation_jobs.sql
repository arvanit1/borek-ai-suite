-- AT-37 migration 009: generation_jobs (v2 §23)

CREATE TABLE IF NOT EXISTS generation_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL
    REFERENCES opportunities(id) ON DELETE CASCADE,
  presentation_id UUID
    REFERENCES presentations(id) ON DELETE SET NULL,
  job_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'QUEUED',
  current_stage TEXT NOT NULL DEFAULT 'QUEUED',
  error_code TEXT,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

ALTER TABLE generation_jobs ENABLE ROW LEVEL SECURITY;
