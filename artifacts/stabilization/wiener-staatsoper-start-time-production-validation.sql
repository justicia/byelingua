-- Read-only Wiener start_time validation; DO NOT EXECUTE apply SQL.
WITH targets(event_id,expected_start_time) AS (VALUES
('ba6e5348-ed9e-4826-9403-a94566088e84'::uuid,'19:00'::time),
('fcc2d372-fa77-4ec8-b039-7afa8760a4f2'::uuid,'19:00'::time),
('2d5c3c8c-7e09-4e20-a4aa-bae5792eaf16'::uuid,'19:00'::time),
('0ab9adb5-4421-4358-b0cc-135556873f68'::uuid,'20:15'::time),
('aac9ada7-478a-4b90-a726-2b00e95e7b25'::uuid,'19:00'::time),
('cb521037-4e5c-4ab1-a247-52bc61354519'::uuid,'11:00'::time),
('75eca7b5-2ce0-49f9-a978-09512ef62d46'::uuid,'14:00'::time),
('84c89d5e-6a0e-494b-b11b-bbf89390a26a'::uuid,'19:00'::time),
('d6d3e143-4733-4fa7-b9c3-28c778d99137'::uuid,'19:00'::time),
('b3d9d409-032f-45c8-821b-357b30cd921e'::uuid,'19:00'::time)),
checks(check_name,value) AS (
 SELECT 'target_count',count(*)::text FROM targets
 UNION ALL
 SELECT 'target_events_missing',count(*)::text FROM targets t LEFT JOIN public.events e ON e.id=t.event_id WHERE e.id IS NULL
 UNION ALL
 SELECT 'target_events_outside_wiener',count(*)::text FROM targets t LEFT JOIN public.events e ON e.id=t.event_id LEFT JOIN public.organizations o ON o.id=e.organization_id WHERE e.id IS NOT NULL AND o.slug IS DISTINCT FROM 'wiener-staatsoper'
 UNION ALL
 SELECT 'incorrect_target_times',count(*)::text FROM targets t LEFT JOIN public.events e ON e.id=t.event_id WHERE e.start_time IS DISTINCT FROM t.expected_start_time
 UNION ALL
 SELECT 'remaining_wiener_null_start_time',count(*)::text FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='wiener-staatsoper' AND e.start_time IS NULL
 UNION ALL
 SELECT 'expected_remaining_wiener_null_start_time','302'
)
SELECT check_name,value FROM checks ORDER BY check_name;
