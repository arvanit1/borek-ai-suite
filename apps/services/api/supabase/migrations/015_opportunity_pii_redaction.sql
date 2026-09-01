-- ES-4: per-opportunity PII redaction policy (default safest behavior).

ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS pii_redaction_enabled BOOLEAN NOT NULL DEFAULT true;
