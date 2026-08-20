-- Byelingua Phase 3.7A manual alias apply SQL.
-- Fresh production snapshot: 2026-08-20T13:51:58.223Z
-- No Composer rows are created by this script.
BEGIN;
DO $$
BEGIN
  IF (SELECT count(*) FROM public.composers) <> 295 THEN RAISE EXCEPTION 'Composer master changed since fresh preflight'; END IF;
  IF (SELECT count(*) FROM public.composer_aliases) NOT BETWEEN 75 AND 82 THEN RAISE EXCEPTION 'Alias master changed beyond this batch'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES
        ('c692545f-1e0e-45ab-aa1a-c4d20224b6cc'::uuid, 'A. de Cabezón', '6a12bc7a-ae8b-49a4-bd00-8fced75a3359'::uuid),
        ('2485c789-13fd-4512-a53c-7afe97e13c8a'::uuid, 'A. Márquez', 'a05b4296-c373-48e3-a271-c41eedcb20ca'::uuid),
        ('9075514c-7193-425e-a8e2-0de19d397fa1'::uuid, 'A. Mudarra', 'f1454e54-dfa2-4789-b058-18e3dc414400'::uuid),
        ('6a886569-c942-4ec5-91a9-edee1e1e41c2'::uuid, 'A. Villamil', '53ed881c-f046-4382-9d4e-cd2c3ea8f5fc'::uuid),
        ('bbd8de84-3248-432b-b73e-fc3fc5049446'::uuid, 'A. Vivas', 'be41f94d-1725-4bb0-85c9-bf5d5537fed8'::uuid),
        ('2c3d1af1-43b3-4747-9512-15d72a60d70e'::uuid, 'Agustín Pío Barrios "Mangoré"', '0b7adb05-cc92-4eef-be61-d2900d9c3749'::uuid),
        ('4f89d8df-3778-4247-90e8-a34516ab7cb8'::uuid, 'Alexandre Glazounov', '8d5e083f-c7e8-4214-aab2-83f5a5377da8'::uuid),
        ('ae5befaf-f76d-4328-87b1-83bcc0bfefc9'::uuid, 'Alexandre Scriabine', 'b556fb8c-fcaa-4a20-b2c0-aadc6f756519'::uuid),
        ('132909ba-c4c5-46ce-9f54-18a7a6df16aa'::uuid, 'Arnold Schoenberg', '47af8fcc-1a70-4231-afc1-c1d2a5dcdd67'::uuid),
        ('1fa88ce1-2dd8-4d92-9fb6-695f3fa9e196'::uuid, 'Beethoven', 'cf66deb2-f6b4-4136-a1be-6c8e4b741e59'::uuid),
        ('cc5196e2-5dbe-4701-955e-1d02c237f2ed'::uuid, 'BEETHOVEN', 'cf66deb2-f6b4-4136-a1be-6c8e4b741e59'::uuid),
        ('85237c38-3409-4331-871a-2caa71bb0f0e'::uuid, 'BRAHMS', '2cffa372-2bc9-4321-bf4e-4a17aa772418'::uuid),
        ('7ffc6e88-b59d-42d9-abab-9bc3ae84485b'::uuid, 'C. Debussy', '36ec6fc4-e55c-4e87-80c8-01402609b286'::uuid),
        ('41136890-44a8-44a2-893f-cd88afbc481a'::uuid, 'C. Saint-Saëns', 'caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88'::uuid),
        ('25ec6235-20de-4099-a63d-0d7015d6095b'::uuid, 'Chaikovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('63ec92a8-ae04-4e6a-9a60-de056855390e'::uuid, 'CHAIKOVSKI', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('4c5c918d-68c3-44cb-af3c-76cf673f4669'::uuid, 'Chopin', '63c53106-3321-4af3-8d17-b04806facc1c'::uuid),
        ('e808a14a-139e-4b0f-a63b-b7f8c86bf600'::uuid, 'D. Scarlatti', '5c2d8dee-1703-4f36-b745-4a002eef9465'::uuid),
        ('adb36800-ef36-481d-87cd-6d682546c01c'::uuid, 'Dimitri Shostakovich', '6f3e72be-6184-4334-b642-35736ff5ad1c'::uuid),
        ('642ef633-9045-4b48-8771-2218a0ba845e'::uuid, 'Dmitri Chostakovitch', '6f3e72be-6184-4334-b642-35736ff5ad1c'::uuid),
        ('a2512739-42e8-4cc8-9f99-f935a7e6b1a9'::uuid, 'Dmitri Shostakóvich', '6f3e72be-6184-4334-b642-35736ff5ad1c'::uuid),
        ('8e478d44-d3af-4060-b17f-a0849dfbec19'::uuid, 'Dvořák', 'b939d48a-1989-462a-b29b-4a554213875d'::uuid),
        ('af51b5aa-3746-4d46-84a8-8462ec97a1ac'::uuid, 'DVOŘÁK', 'b939d48a-1989-462a-b29b-4a554213875d'::uuid),
        ('2df162d1-d39a-4744-a5e6-dbac0644bb65'::uuid, 'Eliane Radigue', '84bf80c5-5038-4e19-be52-b06a8c5b61a3'::uuid),
        ('69bdac1f-032a-4576-a82e-54e51573cbb8'::uuid, 'Falla', 'eb7b90d2-17ff-4c20-9f98-eb6df9f790c6'::uuid),
        ('bab2dbe2-1f95-46d9-9c04-cb119b57a7e7'::uuid, 'Felix Mendelssohn-Bartholdy', 'c4945f2d-cb41-41aa-ac71-9ef544ffac7f'::uuid),
        ('ead8c9d2-e33a-47c5-a875-2d2637775db3'::uuid, 'Florence Beatrice Price', 'cdf17dc1-8e37-4f70-ad84-dc27c08e013f'::uuid),
        ('4ffed86b-f988-4897-8a68-777336921330'::uuid, 'Francesco Cilèa', 'b3dfe085-db64-40ce-9d95-86af10831b69'::uuid),
        ('a3f1f110-c681-47b3-a961-cc1a21db2474'::uuid, 'Franz Joseph Haydn', '18abcf6f-7dae-45db-944f-c6d6fdf2278a'::uuid),
        ('4c0910c3-c02b-4976-9ced-07879d90a394'::uuid, 'G. Holst', '5efcffbe-c47d-474d-9816-d107c43245f2'::uuid),
        ('12f156e1-c6f1-4780-a80f-cf94680b5e34'::uuid, 'Galina Oustvolskaïa', 'b0a03f67-594e-4752-8fa9-f178aee304a5'::uuid),
        ('3db5547d-739d-4387-85c4-ba4dc18476a6'::uuid, 'Georg Friedrich Haendel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'::uuid),
        ('a83fe772-5bf5-4501-bac7-2d53b4e8a14c'::uuid, 'George Frideric Haendel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'::uuid),
        ('2bfe0574-7a8a-466d-a58f-60c1818674e8'::uuid, 'Gershwin', '1e87f81e-dbd6-4b5c-8eab-2287cf159149'::uuid),
        ('130110b2-980a-4d37-9da5-8e532f861a77'::uuid, 'Grażina Bacewizc', 'cbf6738b-5799-4a61-b3cf-c3e2176a9ef0'::uuid),
        ('23de8768-1165-452b-8ad0-8621e4c85e5b'::uuid, 'Händel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'::uuid),
        ('e5e0ac69-2eab-43fc-b61b-2085ed314199'::uuid, 'I. Carreño', 'bd70bc90-0178-4e08-8ce0-6d00538580b0'::uuid),
        ('837c909f-fe00-4a7f-8b70-02c5c8fc12e2'::uuid, 'Igor Stravinsky', '851a746a-4c9d-4f9e-a401-d85bd9a26dc8'::uuid),
        ('6a65ec3f-55a3-46fe-b949-5df4d1c352be'::uuid, 'J. Brahms', '2cffa372-2bc9-4321-bf4e-4a17aa772418'::uuid),
        ('a9442149-422c-42db-8295-5f4833401d4e'::uuid, 'J. S. Bach', '0cb43b06-7258-4cb5-84cd-ab7f79e407e4'::uuid),
        ('012422be-c717-4b79-b51a-6850d4e68b00'::uuid, 'J.-P. Rameau', '3860f2ba-6650-4e38-b61c-2b55a3b9a447'::uuid),
        ('ac351b78-f08d-4991-94f8-456f00f0198b'::uuid, 'J.S. Bach', '0cb43b06-7258-4cb5-84cd-ab7f79e407e4'::uuid),
        ('6f2b23f9-58e5-44ad-9aa4-dc30d6017daa'::uuid, 'Jean-Baptiste Pergolèse', 'f03a90eb-30f0-49a9-89ef-2c4a20642322'::uuid),
        ('5345fb3b-a9e5-4797-808e-63bb468edb12'::uuid, 'Johann Strauß', 'f49a8515-7b64-4d8d-8129-9233cd627a25'::uuid),
        ('e5abd281-18a8-4427-b964-ae923068d204'::uuid, 'Josef Jongen', '79e444a1-7a70-4aff-832e-c717d90d7a40'::uuid),
        ('c9e96c47-d62f-43a4-b3fb-3ef0ba357064'::uuid, 'Joseph Hellmesberger Jr', 'f438aa99-dd48-496f-b02f-f34597e4078e'::uuid),
        ('36edb11b-95c3-4c6e-802f-3d275aa3ef06'::uuid, 'Leos Janácek', '01b5135b-0613-4a5e-9cff-d32fa11364b6'::uuid),
        ('1464d900-4c00-43a0-9391-033a75448169'::uuid, 'Leoš Janácek', '01b5135b-0613-4a5e-9cff-d32fa11364b6'::uuid),
        ('58a61c6a-f0d3-4016-befd-53e9809628d4'::uuid, 'Louis-Joseph-Ferdinand Hérold', '14ce37ad-8bc4-4627-b1b9-7540a7c8d3ce'::uuid),
        ('581f562e-512b-4fb0-a1e8-c7bd7ba2bf74'::uuid, 'Luigi Maurizio', '1e06f0c1-1a6c-4b6d-adcf-0cbb3af0f91b'::uuid),
        ('c2f9aecf-a6e3-42f1-80be-156389f73fec'::uuid, 'M. de Falla', 'eb7b90d2-17ff-4c20-9f98-eb6df9f790c6'::uuid),
        ('fc0f4081-dbae-41b1-8b1b-103e68846ba4'::uuid, 'M. Ravel', 'f372a0dd-f851-4339-a8ca-5dc15e1ab508'::uuid),
        ('09689df7-0d3c-4ed0-b922-b42820c5019f'::uuid, 'M. Weinberg', '8a32bf1a-1d54-4f5c-959d-222768b113d3'::uuid),
        ('c31f0edc-dba0-40f8-9316-0c66c77e202e'::uuid, 'Modeste Moussorgski', '536dd1a3-b974-4c50-b6d9-30021397fa58'::uuid),
        ('fa198d41-9979-4f95-8976-48cbb118fcc6'::uuid, 'Mozart', '8fa0e4e1-883d-468e-a062-c743b7601a1f'::uuid),
        ('36a4ac2b-9b89-48b6-a72f-65efb58e4b18'::uuid, 'MOZART', '8fa0e4e1-883d-468e-a062-c743b7601a1f'::uuid),
        ('9665e892-7d36-4a94-996f-09ef7d69a9ab'::uuid, 'Nikolaï Rimski-Korsakov', 'da3c5b27-e804-41ad-8165-59cd4cc01223'::uuid),
        ('87a54419-0f43-42a0-8c22-120f8e0a878a'::uuid, 'P. Glass', 'af91b8cf-61c9-4ab7-93c2-bf8f0f0b9ce4'::uuid),
        ('2d7046eb-63e3-4b88-bd37-26fea3b9fa53'::uuid, 'Piotr Ilich Chaikovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('efbac670-f393-4078-b371-bfd604d6e83b'::uuid, 'Piotr Ilyitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('e752ad6e-0b64-46c1-b44b-e56d3e7d7efb'::uuid, 'Piotr Ilytch Tchaïkovsky', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('79dff188-ebf9-4e05-a6e4-43b1b63540d0'::uuid, 'Pjotr I. Tschaikowski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('56685538-8015-4d0e-9747-5b45d39a9e75'::uuid, 'Ralph Vaughan-Williams', '08e4d35a-f9f5-4b56-bf6d-7c5cc82d295d'::uuid),
        ('37f5aff6-2323-4a72-8878-1bcb5811be46'::uuid, 'Raymond Murray Schafer', 'f2a1e385-808b-4981-995e-8f313d742cba'::uuid),
        ('bdd1e21d-0d3c-4a7d-a4a5-e82a263c1873'::uuid, 'Raymond Murray Shafer', 'f2a1e385-808b-4981-995e-8f313d742cba'::uuid),
        ('2f4785aa-36b7-43a3-8597-4edd7340ff49'::uuid, 'Respighi', '1cf06f21-9da5-4217-a40e-71b2c6b6a03f'::uuid),
        ('dcfc14dd-4133-49f8-9de8-de3e663cdba7'::uuid, 'Sergei Rachmaninow', 'b8f76a6d-c74a-422a-86b3-95922120167c'::uuid),
        ('93a48243-628f-4994-abbd-1a6f7f763a7d'::uuid, 'Sergueï Bortkiewicz', '3da4e0c4-41bf-48c4-bccd-633486ad7857'::uuid),
        ('6152c0e4-1a1c-49ef-8d57-ee06b1a51b6b'::uuid, 'Serguei Rachmaninov', 'b8f76a6d-c74a-422a-86b3-95922120167c'::uuid),
        ('c81d0547-c0b6-49ad-bb89-c11e23ad5dd0'::uuid, 'Serguéi Rajmáninov', 'b8f76a6d-c74a-422a-86b3-95922120167c'::uuid),
        ('97de8d73-eacf-4b7d-a32b-9d256c7cd595'::uuid, 'Sibelius', '70d6ff5d-a60c-4f1a-882d-176e87a39c56'::uuid),
        ('d556a930-88ce-4afe-a60c-1b56e96c6288'::uuid, 'Sofia Goubaïdoulina', 'c3d79632-6684-4a6a-8696-4c9adbaf4cf6'::uuid),
        ('b27960f1-3804-4662-a70d-a3b4f3c6fb49'::uuid, 'W. Byrd', '30dd9f4f-1906-412f-950a-497dbfa0474f'::uuid),
        ('85dd17fb-5593-4e17-85bb-6dd3369e7f73'::uuid, 'Wolfgang A. Mozart', '8fa0e4e1-883d-468e-a062-c743b7601a1f'::uuid),
        ('8196aa4d-463c-4cf1-8103-645698e2d6cb'::uuid, 'Woodkid', '88232afc-3a1d-48a3-ae12-5421449ab9b4'::uuid)
  ) s(id, alias, composer_id) WHERE NOT EXISTS (SELECT 1 FROM public.composer_aliases ca WHERE ca.id=s.id AND ca.alias=s.alias AND ca.composer_id=s.composer_id)) THEN RAISE EXCEPTION 'Existing alias master changed since preflight'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES
        ('Chaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('Piotr I. Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('Saint-Saëns', 'Camille Saint-Saëns', 'caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88'::uuid),
        ('Piotr Ilich Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('George Frideric Händel', 'Georg Friedrich Händel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'::uuid),
        ('Modest Mussorgski', 'Modest Mussorgsky', '536dd1a3-b974-4c50-b6d9-30021397fa58'::uuid)
  ) s(alias, canonical_name, composer_id) LEFT JOIN public.composers c ON c.id=s.composer_id WHERE c.id IS NULL OR c.canonical_name<>s.canonical_name) THEN RAISE EXCEPTION 'Alias target Composer changed'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES
        ('Chaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('Piotr I. Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('Saint-Saëns', 'Camille Saint-Saëns', 'caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88'::uuid),
        ('Piotr Ilich Tchaikovsky', 'Piotr Ilitch Tchaïkovski', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('George Frideric Händel', 'Georg Friedrich Händel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'::uuid),
        ('Modest Mussorgski', 'Modest Mussorgsky', '536dd1a3-b974-4c50-b6d9-30021397fa58'::uuid)
  ) s(alias, canonical_name, composer_id) JOIN public.composer_aliases ca ON ca.alias=s.alias WHERE ca.composer_id<>s.composer_id) THEN RAISE EXCEPTION 'Alias collision with another Composer'; END IF;
END $$;
INSERT INTO public.composer_aliases (composer_id, alias, source)
SELECT s.composer_id, s.alias, 'auditorio_nacional_phase3.7A'
FROM (VALUES
        ('Chaikovsky', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('Piotr I. Tchaikovsky', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('Saint-Saëns', 'caf15bf4-07ea-4fdf-b7bf-54b0b6b5cc88'::uuid),
        ('Piotr Ilich Tchaikovsky', '8b8442d0-dd77-4c59-ab2e-d897abb10408'::uuid),
        ('George Frideric Händel', '8cfdf8f7-929a-48bc-9400-cd88d41c5904'::uuid),
        ('Modest Mussorgski', '536dd1a3-b974-4c50-b6d9-30021397fa58'::uuid)
) s(alias, composer_id)
WHERE NOT EXISTS (SELECT 1 FROM public.composer_aliases ca WHERE ca.alias=s.alias AND ca.composer_id=s.composer_id)
RETURNING id, composer_id, alias;
COMMIT;







