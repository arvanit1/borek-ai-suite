-- AT-58: persist and constrain validated client-logo pixel dimensions.

ALTER TABLE opportunity_client_logos
  ADD COLUMN IF NOT EXISTS width_px INTEGER;

ALTER TABLE opportunity_client_logos
  ADD COLUMN IF NOT EXISTS height_px INTEGER;

ALTER TABLE opportunity_client_logos
  DROP CONSTRAINT IF EXISTS opportunity_client_logos_width_px_range;
ALTER TABLE opportunity_client_logos
  ADD CONSTRAINT opportunity_client_logos_width_px_range
    CHECK (
      width_px IS NULL
      OR (width_px >= 64 AND width_px <= 4096)
    );

ALTER TABLE opportunity_client_logos
  DROP CONSTRAINT IF EXISTS opportunity_client_logos_height_px_range;
ALTER TABLE opportunity_client_logos
  ADD CONSTRAINT opportunity_client_logos_height_px_range
    CHECK (
      height_px IS NULL
      OR (height_px >= 64 AND height_px <= 4096)
    );
