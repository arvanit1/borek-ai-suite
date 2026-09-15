-- MS-32: owner-scoped project facts used to render a follow-up review fixture.

ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS followup_statics JSONB;

ALTER TABLE opportunities
  DROP CONSTRAINT IF EXISTS opportunities_followup_statics_object;
ALTER TABLE opportunities
  ADD CONSTRAINT opportunities_followup_statics_object
  CHECK (
    followup_statics IS NULL
    OR jsonb_typeof(followup_statics) = 'object'
  );
