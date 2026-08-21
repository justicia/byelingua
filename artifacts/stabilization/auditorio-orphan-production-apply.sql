-- Auditorio orphan production SQL; DO NOT EXECUTE IN THIS TASK.
-- database_writes = 0. This is the only executable Auditorio Event delete.
BEGIN;
DO $$
DECLARE candidate public.events%ROWTYPE; survivor public.events%ROWTYPE; n integer;
BEGIN
 SELECT e.* INTO candidate FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE e.id='ab000640-fb8e-43ba-850b-c3da076f00b9'::uuid AND o.slug='auditorio-nacional-inaem';
 SELECT e.* INTO survivor FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE e.id='f6778b5d-1f92-4089-b5cb-1567f47c3da5'::uuid AND o.slug='auditorio-nacional-inaem';
 IF candidate.id IS NULL OR survivor.id IS NULL THEN RAISE EXCEPTION 'Auditorio orphan candidate/survivor missing or outside organization'; END IF;
 IF candidate.date IS DISTINCT FROM DATE '2026-10-13' OR candidate.start_time IS DISTINCT FROM TIME '19:30' OR candidate.title IS DISTINCT FROM 'Ibermúsica. Filarmónica de Nueva York' OR candidate.room IS DISTINCT FROM 'Sala Sinfónica' THEN RAISE EXCEPTION 'Auditorio orphan exact candidate identity changed'; END IF;
 IF candidate.date IS DISTINCT FROM survivor.date OR candidate.start_time IS DISTINCT FROM survivor.start_time OR candidate.title IS DISTINCT FROM survivor.title OR candidate.room IS DISTINCT FROM survivor.room THEN RAISE EXCEPTION 'Auditorio orphan candidate/survivor identity differs'; END IF;
 SELECT count(*) INTO n FROM public.event_sources WHERE event_id=candidate.id; IF n<>0 THEN RAISE EXCEPTION 'event_sources dependency appeared: %',n; END IF;
 SELECT count(*) INTO n FROM public.event_programme WHERE event_id=candidate.id; IF n<>0 THEN RAISE EXCEPTION 'event_programme dependency appeared: %',n; END IF;
 SELECT count(*) INTO n FROM public.event_credits WHERE event_id=candidate.id; IF n<>0 THEN RAISE EXCEPTION 'event_credits dependency appeared: %',n; END IF;
 SELECT count(*) INTO n FROM public.user_event_relations WHERE event_id=candidate.id; IF n<>0 THEN RAISE EXCEPTION 'user_event_relations dependency appeared: %',n; END IF;
 SELECT count(*) INTO n FROM public.schedule_events WHERE event_id=candidate.id; IF n<>0 THEN RAISE EXCEPTION 'schedule_events dependency appeared: %',n; END IF;
 DELETE FROM public.events e USING public.organizations o WHERE e.id=candidate.id AND e.organization_id=o.id AND o.slug='auditorio-nacional-inaem';
 GET DIAGNOSTICS n = ROW_COUNT;
 IF n<>1 THEN RAISE EXCEPTION 'Auditorio orphan DELETE ROW_COUNT expected 1, got %',n; END IF;
 IF (SELECT count(*) FROM public.events WHERE id=candidate.id)<>0 THEN RAISE EXCEPTION 'Auditorio orphan candidate remains'; END IF;
 IF (SELECT count(*) FROM public.events WHERE id=survivor.id)<>1 THEN RAISE EXCEPTION 'Auditorio orphan survivor missing'; END IF;
END $$;
COMMIT;
