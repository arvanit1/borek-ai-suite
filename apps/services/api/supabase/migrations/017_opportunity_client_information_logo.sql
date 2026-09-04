-- AT-58: optional opportunity client context and private client logos.

ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS additional_client_information JSONB;

ALTER TABLE opportunities
  DROP CONSTRAINT IF EXISTS opportunities_additional_client_information_object;
ALTER TABLE opportunities
  ADD CONSTRAINT opportunities_additional_client_information_object
  CHECK (
    additional_client_information IS NULL
    OR jsonb_typeof(additional_client_information) = 'object'
  );

CREATE TABLE IF NOT EXISTS opportunity_client_logos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL UNIQUE REFERENCES opportunities(id) ON DELETE CASCADE,
  created_by UUID NOT NULL,
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL CHECK (mime_type IN ('image/png', 'image/jpeg', 'image/webp')),
  size_bytes BIGINT NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 5242880),
  storage_path TEXT NOT NULL UNIQUE,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE opportunity_client_logos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_own_opportunity_client_logos" ON opportunity_client_logos;
CREATE POLICY "users_own_opportunity_client_logos"
  ON opportunity_client_logos
  FOR ALL
  TO authenticated
  USING (
    created_by = auth.uid()
    AND opportunity_id IN (
      SELECT id FROM opportunities WHERE created_by = auth.uid()
    )
  )
  WITH CHECK (
    created_by = auth.uid()
    AND opportunity_id IN (
      SELECT id FROM opportunities WHERE created_by = auth.uid()
    )
  );

INSERT INTO storage.buckets (id, name, public)
VALUES ('client-logos', 'client-logos', false)
ON CONFLICT (id) DO UPDATE SET public = false;

DROP POLICY IF EXISTS "users_own_client_logo_objects" ON storage.objects;
CREATE POLICY "users_own_client_logo_objects"
  ON storage.objects
  FOR ALL
  TO authenticated
  USING (
    bucket_id = 'client-logos'
    AND (storage.foldername(name))[1] IN (
      SELECT id::text FROM opportunities WHERE created_by = auth.uid()
    )
  )
  WITH CHECK (
    bucket_id = 'client-logos'
    AND (storage.foldername(name))[1] IN (
      SELECT id::text FROM opportunities WHERE created_by = auth.uid()
    )
  );
