-- BT-25: durable, race-safe opt-in for Plan-to-Presentation continuation.

ALTER TABLE generation_jobs
  ADD COLUMN IF NOT EXISTS auto_continue BOOLEAN NOT NULL DEFAULT FALSE;
