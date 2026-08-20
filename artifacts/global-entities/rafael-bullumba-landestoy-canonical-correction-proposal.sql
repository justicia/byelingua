-- Byelingua Phase 3.7A.2 manual canonical correction SQL.
-- Execute manually only after review. This updates one existing Composer row.
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM public.composers
    WHERE id = '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid
      AND canonical_name = 'Rafael Bullumba Landestroy'
      AND identity_key = 'composer:5cb2460f4dd873d6236c481787dd02ee'
  ) THEN
    RAISE EXCEPTION 'Expected Rafael Bullumba Landestroy row was not found';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.composers
    WHERE canonical_name = 'Rafael Bullumba Landestoy'
      AND id <> '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid
  ) THEN
    RAISE EXCEPTION 'Corrected canonical name collision';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.composers
    WHERE identity_key = 'composer:cb0ff5c4f2aabadfb9745dbc5de6b159'
      AND id <> '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid
  ) THEN
    RAISE EXCEPTION 'Corrected identity_key collision';
  END IF;
END $$;

WITH updated AS (
  UPDATE public.composers
  SET canonical_name = 'Rafael Bullumba Landestoy',
      identity_key = 'composer:cb0ff5c4f2aabadfb9745dbc5de6b159',
      updated_at = now()
  WHERE id = '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid
    AND canonical_name = 'Rafael Bullumba Landestroy'
    AND identity_key = 'composer:5cb2460f4dd873d6236c481787dd02ee'
  RETURNING id
)
SELECT CASE WHEN count(*) = 1 THEN 'updated_one_composer' ELSE 'unexpected_update_count' END AS result,
       count(*) AS updated_rows
FROM updated;

DO $$
DECLARE
  updated_count integer;
BEGIN
  SELECT count(*) INTO updated_count
  FROM public.composers
  WHERE id = '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid
    AND canonical_name = 'Rafael Bullumba Landestoy'
    AND identity_key = 'composer:cb0ff5c4f2aabadfb9745dbc5de6b159';
  IF updated_count <> 1 THEN
    RAISE EXCEPTION 'Canonical correction did not produce exactly one corrected row';
  END IF;
END $$;

COMMIT;

