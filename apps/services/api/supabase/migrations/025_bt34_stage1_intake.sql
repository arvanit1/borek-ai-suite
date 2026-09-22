-- BT-34: additive, nullable intake; existing opportunity ownership/RLS applies.
ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS stage1_intake JSONB;

ALTER TABLE opportunities
  DROP CONSTRAINT IF EXISTS opportunities_stage1_intake_object;
ALTER TABLE opportunities
  ADD CONSTRAINT opportunities_stage1_intake_object
  CHECK (stage1_intake IS NULL OR jsonb_typeof(stage1_intake) = 'object');
