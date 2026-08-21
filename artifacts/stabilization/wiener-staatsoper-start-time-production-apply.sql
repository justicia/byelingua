-- FINAL STABILIZATION PRODUCTION SQL; DO NOT EXECUTE IN THIS TASK.
BEGIN;
CREATE TEMP TABLE _wiener_time_targets(event_id uuid PRIMARY KEY,event_date date,title text,start_time time,source_event_id text,source_url text,official_evidence_url text,official_raw_time text) ON COMMIT DROP;
INSERT INTO _wiener_time_targets VALUES
('ba6e5348-ed9e-4826-9403-a94566088e84'::uuid,'2026-09-19'::date,'Impulse','19:00'::time,'impulse:2026-09-19','https://www.wiener-staatsoper.at/en/calendar/detail/impulse/2026-09-19/','https://www.wiener-staatsoper.at/en/calendar/2026/september/','19:00—21:45'),
('fcc2d372-fa77-4ec8-b039-7afa8760a4f2'::uuid,'2027-01-29'::date,'Living Legacies','19:00'::time,'living-legacies:2027-01-29','https://www.wiener-staatsoper.at/en/calendar/detail/living-legacies/2027-01-29/','https://www.wiener-staatsoper.at/en/calendar/2027/january/','19:00'),
('2d5c3c8c-7e09-4e20-a4aa-bae5792eaf16'::uuid,'2027-01-30'::date,'Don Giovanni','19:00'::time,'don-giovanni:2027-01-30','https://www.wiener-staatsoper.at/en/calendar/detail/don-giovanni/2027-01-30/','https://www.wiener-staatsoper.at/en/calendar/2027/january/','19:00'),
('0ab9adb5-4421-4358-b0cc-135556873f68'::uuid,'2027-02-04'::date,'Vienna Opera Ball','20:15'::time,'vienna-opera-ball:2027-02-04','https://www.wiener-staatsoper.at/en/calendar/detail/vienna-opera-ball/2027-02-04/','https://www.wiener-staatsoper.at/en/calendar/detail/vienna-opera-ball/2027-02-04/','20:15'),
('aac9ada7-478a-4b90-a726-2b00e95e7b25'::uuid,'2027-02-12'::date,'Der Rosen­kavalier','19:00'::time,'der-rosenkavalier:2027-02-12','https://www.wiener-staatsoper.at/en/calendar/detail/der-rosenkavalier/2027-02-12/','https://www.wiener-staatsoper.at/en/calendar/2027/february/','19:00—20:30'),
('cb521037-4e5c-4ab1-a247-52bc61354519'::uuid,'2027-02-14'::date,'Matinee zu Ballo in maschera','11:00'::time,'matinee-zu-ballo-in-maschera:2027-02-14','https://www.wiener-staatsoper.at/en/calendar/detail/matinee-zu-ballo-in-maschera/2027-02-14/','https://www.wiener-staatsoper.at/en/calendar/2027/february/','11:00—12:30'),
('75eca7b5-2ce0-49f9-a978-09512ef62d46'::uuid,'2027-02-28'::date,'Workout in der Oper','14:00'::time,'workout-in-der-oper:2027-02-28','https://www.wiener-staatsoper.at/en/calendar/detail/workout-in-der-oper/2027-02-28/','https://www.wiener-staatsoper.at/en/calendar/2027/february/','14:00'),
('84c89d5e-6a0e-494b-b11b-bbf89390a26a'::uuid,'2027-04-27'::date,'Woolf Works','19:00'::time,'woolf-works:2027-04-27','https://www.wiener-staatsoper.at/en/calendar/detail/woolf-works/2027-04-27/','https://www.wiener-staatsoper.at/en/calendar/2027/april/','19:00—20:10'),
('d6d3e143-4733-4fa7-b9c3-28c778d99137'::uuid,'2027-05-21'::date,'Woolf Works','19:00'::time,'woolf-works:2027-05-21','https://www.wiener-staatsoper.at/en/calendar/detail/woolf-works/2027-05-21/','https://www.wiener-staatsoper.at/en/calendar/2027/may/','19:00—21:00'),
('b3d9d409-032f-45c8-821b-357b30cd921e'::uuid,'2027-06-16'::date,'Woolf Works','19:00'::time,'woolf-works:2027-06-16','https://www.wiener-staatsoper.at/en/calendar/detail/woolf-works/2027-06-16/','https://www.wiener-staatsoper.at/en/calendar/2027/june/','19:00');
DO $$ BEGIN
 IF (SELECT count(*) FROM _wiener_time_targets)<>10 THEN RAISE EXCEPTION 'Expected 10 start_time targets'; END IF;
 IF EXISTS (SELECT 1 FROM _wiener_time_targets t LEFT JOIN public.events e ON e.id=t.event_id LEFT JOIN public.organizations o ON o.id=e.organization_id WHERE e.id IS NULL OR o.slug<>'wiener-staatsoper' OR e.date IS DISTINCT FROM t.event_date OR e.title IS DISTINCT FROM t.title OR e.start_time IS NOT NULL OR NOT EXISTS (SELECT 1 FROM public.event_sources es WHERE es.event_id=t.event_id AND es.source_event_id=t.source_event_id AND es.source_url=t.source_url)) THEN RAISE EXCEPTION 'start_time target or source identity changed'; END IF;
END $$;
DO $$ DECLARE n integer; BEGIN
 UPDATE public.events e SET start_time=t.start_time FROM _wiener_time_targets t JOIN public.organizations o ON o.slug='wiener-staatsoper' WHERE e.id=t.event_id AND e.organization_id=o.id AND e.start_time IS NULL;
 GET DIAGNOSTICS n = ROW_COUNT;
 IF n<>10 THEN RAISE EXCEPTION 'Wiener start_time UPDATE ROW_COUNT expected 10, got %',n; END IF;
 IF EXISTS (SELECT 1 FROM _wiener_time_targets t JOIN public.events e ON e.id=t.event_id WHERE e.start_time IS DISTINCT FROM t.start_time) THEN RAISE EXCEPTION 'Staged updates have incorrect exact times'; END IF;
 IF (SELECT count(*) FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='wiener-staatsoper' AND e.start_time IS NULL)<>302 THEN RAISE EXCEPTION 'Expected 302 remaining NULL start_time'; END IF;
END $$;
COMMIT;
