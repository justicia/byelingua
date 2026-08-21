-- Read-only Paris Opera validation; DO NOT EXECUTE apply SQL.
SELECT count(*) AS events FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='opera-national-de-paris';
SELECT e.event_type,count(*) FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='opera-national-de-paris' GROUP BY e.event_type;
SELECT count(*) AS null_or_unexpected FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='opera-national-de-paris' AND (e.event_type IS NULL OR e.event_type NOT IN ('ballet','concert_recital','young_audience','opera','encounter','rehearsal'));
