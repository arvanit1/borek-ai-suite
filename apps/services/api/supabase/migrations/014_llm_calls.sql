-- AT-53: durable LLM call metadata (no prompt/response bodies).
-- Numbered 014 because 012/013 already exist (transcript storage, job runtime fields).

CREATE TABLE IF NOT EXISTS llm_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id TEXT NOT NULL,
  job_id UUID REFERENCES generation_jobs(id)
    ON DELETE SET NULL,
  opportunity_id UUID REFERENCES opportunities(id)
    ON DELETE CASCADE,
  stage TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  total_tokens INTEGER,
  latency_ms INTEGER,
  retry_count INTEGER DEFAULT 0,
  status TEXT NOT NULL,
  error_category TEXT,
  estimated_cost_eur NUMERIC(10,6),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_own_llm_calls" ON llm_calls;
CREATE POLICY "users_own_llm_calls"
  ON llm_calls FOR ALL
  USING (
    opportunity_id IN (
      SELECT id FROM opportunities
      WHERE created_by = auth.uid()
    )
  );

ALTER TABLE generation_jobs
  ADD COLUMN IF NOT EXISTS llm_cost_eur NUMERIC(10, 6) NOT NULL DEFAULT 0;
