-- Byelingua Phase 3.7A.2 read-only canonical correction validation.
SELECT id, canonical_name, identity_key
FROM public.composers
WHERE id = '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid;

SELECT count(*) AS corrected_uuid_match_count
FROM public.composers
WHERE id = '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid
  AND canonical_name = 'Rafael Bullumba Landestoy'
  AND identity_key = 'composer:cb0ff5c4f2aabadfb9745dbc5de6b159';

SELECT count(*) AS old_canonical_row_count
FROM public.composers
WHERE canonical_name = 'Rafael Bullumba Landestroy';

SELECT count(*) AS old_identity_key_row_count
FROM public.composers
WHERE identity_key = 'composer:5cb2460f4dd873d6236c481787dd02ee';

SELECT count(*) AS new_canonical_collision_count
FROM public.composers
WHERE canonical_name = 'Rafael Bullumba Landestoy';

SELECT count(*) AS new_identity_key_collision_count
FROM public.composers
WHERE identity_key = 'composer:cb0ff5c4f2aabadfb9745dbc5de6b159';

SELECT count(*) AS aliases_still_on_rafael_uuid
FROM public.composer_aliases
WHERE composer_id = '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid;

