-- Byelingua Phase 3.5R read-only validation SQL.
-- Expected Composer inserts: 10; expected alias inserts: 9.
SELECT count(*) AS composer_rows_after_apply FROM public.composers;
SELECT count(*) AS alias_rows_after_apply FROM public.composer_aliases;
WITH intended(canonical_name,identity_key) AS (VALUES ('Arturo Márquez', 'composer:35596264768e193f73a6464f37ca0552'),
        ('Andrés Villamil', 'composer:c2ac784233aba86f02c760ab322d7f10'),
        ('Alejandro Vivas Puig', 'composer:1f3523c25653c570751b9fc9183e7990'),
        ('Agustín Pío Barrios', 'composer:df4328c7761cf640961a870f207b98ae'),
        ('Gustav Holst', 'composer:bbc1073a0072b7007aa253af9fb9182f'),
        ('Inocente Carreño', 'composer:184eb5c75a4989343fca61821c780a72'),
        ('Luigi Maurizio Tedeschi', 'composer:9430baea77eec44040fb79d15617d62a'),
        ('Mieczysław Weinberg', 'composer:d034fb4b61c314fd7126bc86fef9aad9'),
        ('Nuria Núñez Hierro', 'composer:ab6c5f55a441baf1c3b07ac9291ce61b'),
        ('Ottorino Respighi', 'composer:245e242a641d08377d24e984e21ad587')) SELECT i.canonical_name,c.id,c.identity_key,(c.id IS NOT NULL AND c.identity_key=i.identity_key) AS target_match FROM intended i LEFT JOIN public.composers c ON c.canonical_name=i.canonical_name ORDER BY i.canonical_name;
WITH staged(canonical_name,alias) AS (VALUES ('Arturo Márquez', 'A. Márquez'),
        ('Andrés Villamil', 'A. Villamil'),
        ('Alejandro Vivas Puig', 'A. Vivas'),
        ('Agustín Pío Barrios', 'Agustín Pío Barrios "Mangoré"'),
        ('Gustav Holst', 'G. Holst'),
        ('Inocente Carreño', 'I. Carreño'),
        ('Luigi Maurizio Tedeschi', 'Luigi Maurizio'),
        ('Mieczysław Weinberg', 'M. Weinberg'),
        ('Ottorino Respighi', 'Respighi')) SELECT s.alias,c.id AS composer_id,c.canonical_name,(c.canonical_name=s.canonical_name) AS target_match FROM staged s LEFT JOIN public.composer_aliases ca ON ca.alias=s.alias LEFT JOIN public.composers c ON c.id=ca.composer_id WHERE s.alias IS NOT NULL ORDER BY s.alias;
SELECT count(*) AS duplicate_exact_canonical_names FROM (SELECT canonical_name FROM public.composers GROUP BY canonical_name HAVING count(*)>1) x;
SELECT count(*) AS orphan_aliases FROM public.composer_aliases ca LEFT JOIN public.composers c ON c.id=ca.composer_id WHERE c.id IS NULL;
WITH intended(canonical_name,identity_key) AS (VALUES ('Arturo Márquez', 'composer:35596264768e193f73a6464f37ca0552'),
        ('Andrés Villamil', 'composer:c2ac784233aba86f02c760ab322d7f10'),
        ('Alejandro Vivas Puig', 'composer:1f3523c25653c570751b9fc9183e7990'),
        ('Agustín Pío Barrios', 'composer:df4328c7761cf640961a870f207b98ae'),
        ('Gustav Holst', 'composer:bbc1073a0072b7007aa253af9fb9182f'),
        ('Inocente Carreño', 'composer:184eb5c75a4989343fca61821c780a72'),
        ('Luigi Maurizio Tedeschi', 'composer:9430baea77eec44040fb79d15617d62a'),
        ('Mieczysław Weinberg', 'composer:d034fb4b61c314fd7126bc86fef9aad9'),
        ('Nuria Núñez Hierro', 'composer:ab6c5f55a441baf1c3b07ac9291ce61b'),
        ('Ottorino Respighi', 'composer:245e242a641d08377d24e984e21ad587')) SELECT count(*) AS batch_canonical_target_mismatches FROM intended i LEFT JOIN public.composers c ON c.canonical_name=i.canonical_name WHERE c.id IS NULL OR c.identity_key<>i.identity_key;
WITH staged(canonical_name,alias) AS (VALUES ('Arturo Márquez', 'A. Márquez'),
        ('Andrés Villamil', 'A. Villamil'),
        ('Alejandro Vivas Puig', 'A. Vivas'),
        ('Agustín Pío Barrios', 'Agustín Pío Barrios "Mangoré"'),
        ('Gustav Holst', 'G. Holst'),
        ('Inocente Carreño', 'I. Carreño'),
        ('Luigi Maurizio Tedeschi', 'Luigi Maurizio'),
        ('Mieczysław Weinberg', 'M. Weinberg'),
        ('Ottorino Respighi', 'Respighi')) SELECT count(*) AS batch_alias_target_mismatches FROM staged s LEFT JOIN public.composer_aliases ca ON ca.alias=s.alias LEFT JOIN public.composers c ON c.id=ca.composer_id WHERE s.alias IS NOT NULL AND (c.id IS NULL OR c.canonical_name<>s.canonical_name);
