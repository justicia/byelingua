-- Byelingua Phase 3.7A read-only validation SQL.
-- Expected alias rows after apply: 82
SELECT count(*) AS alias_rows_after_apply FROM public.composer_aliases;
WITH staged(alias, canonical_name, composer_id) AS (VALUES
        ('Chaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'),
        ('Piotr I. Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'),
        ('Saint-Saëns', 'Camille Saint-Saëns', 'caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88'),
        ('Piotr Ilich Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'),
        ('George Frideric Händel', 'Georg Friedrich Händel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'),        ('Modest Mussorgski', 'Modest Mussorgsky', '536dd1a3-b974-4c50-b6d9-30021397fa58')
) SELECT s.alias, s.canonical_name AS target_canonical_name, s.composer_id AS target_composer_id, ca.composer_id AS actual_composer_id, c.canonical_name AS actual_canonical_name, (ca.composer_id=s.composer_id) AS target_match FROM staged s LEFT JOIN public.composer_aliases ca ON ca.alias=s.alias LEFT JOIN public.composers c ON c.id=ca.composer_id ORDER BY s.alias;
WITH staged(alias, canonical_name, composer_id) AS (VALUES
        ('Chaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'),
        ('Piotr I. Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'),
        ('Saint-Saëns', 'Camille Saint-Saëns', 'caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88'),
        ('Piotr Ilich Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'),
        ('George Frideric Händel', 'Georg Friedrich Händel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'),        ('Modest Mussorgski', 'Modest Mussorgsky', '536dd1a3-b974-4c50-b6d9-30021397fa58')
) SELECT count(*) AS batch_alias_target_mismatches FROM staged s LEFT JOIN public.composer_aliases ca ON ca.alias=s.alias WHERE ca.composer_id IS NULL OR ca.composer_id<>s.composer_id;
SELECT count(*) AS orphan_aliases FROM public.composer_aliases ca LEFT JOIN public.composers c ON c.id=ca.composer_id WHERE c.id IS NULL;
-- Normalized alias safety was evaluated with the accepted Python normalizer against the fresh snapshot.
-- Expected normalized alias -> Composer mappings:
-- chaikovsky => 8b8442d0-dd77-4c59-ab2e-d897abb10408 (Piotr Ilitch Tchaïkovski)
-- piotr i tchaikovsky => 8b8442d0-dd77-4c59-ab2e-d897abb10408 (Piotr Ilitch Tchaïkovski)
-- saint saens => caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88 (Camille Saint-Saëns)
-- piotr ilich tchaikovsky => 8b8442d0-dd77-4c59-ab2e-d897abb10408 (Piotr Ilitch Tchaïkovski)
-- george frideric handel => 8cfdf8f7-929a-48bc-9400-cd88d41c5904 (Georg Friedrich Händel)
-- rafael bullumba landestoy => 57fffd2c-b888-4f0c-b2d3-001687c51d61 (Rafael Bullumba Landestroy)
-- modest mussorgski => 536dd1a3-b974-4c50-b6d9-30021397fa58 (Modest Mussorgsky)
WITH expected(normalized_alias, composer_id) AS (VALUES
        ('chaikovsky', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('piotr i tchaikovsky', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('saint saens', 'caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88'::uuid),
        ('piotr ilich tchaikovsky', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('george frideric handel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'::uuid),
        ('rafael bullumba landestoy', '57fffd2c-b888-4f0c-b2d3-001687c51d61'::uuid),
        ('modest mussorgski', '536dd1a3-b974-4c50-b6d9-30021397fa58'::uuid)
) SELECT e.normalized_alias, e.composer_id AS expected_composer_id, count(ca.*) AS exact_alias_rows_after_apply FROM expected e LEFT JOIN public.composer_aliases ca ON ca.alias IN ('Chaikovsky', 'Piotr I. Tchaikovsky', 'Saint-Saëns', 'Piotr Ilich Tchaikovsky', 'George Frideric Händel', 'Rafael Bullumba Landestoy', 'Modest Mussorgski') AND ca.composer_id=e.composer_id GROUP BY e.normalized_alias,e.composer_id ORDER BY e.normalized_alias;



