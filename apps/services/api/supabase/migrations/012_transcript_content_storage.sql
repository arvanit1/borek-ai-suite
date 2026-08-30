-- AT-40 Stage A wiring: stable conversation ids and private transcript objects.

ALTER TABLE transcripts
  ADD COLUMN IF NOT EXISTS conversation_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS transcripts_opportunity_conversation_id_key
  ON transcripts(opportunity_id, conversation_id)
  WHERE conversation_id IS NOT NULL;

INSERT INTO storage.buckets (id, name, public)
VALUES ('transcripts', 'transcripts', false)
ON CONFLICT (id) DO UPDATE SET public = false;

DROP POLICY IF EXISTS "users_own_transcript_objects" ON storage.objects;
CREATE POLICY "users_own_transcript_objects"
  ON storage.objects
  FOR ALL
  TO authenticated
  USING (
    bucket_id = 'transcripts'
    AND (storage.foldername(name))[1] IN (
      SELECT id::text FROM opportunities WHERE created_by = auth.uid()
    )
  )
  WITH CHECK (
    bucket_id = 'transcripts'
    AND (storage.foldername(name))[1] IN (
      SELECT id::text FROM opportunities WHERE created_by = auth.uid()
    )
  );
