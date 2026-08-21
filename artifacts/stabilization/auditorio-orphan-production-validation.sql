-- Read-only Auditorio orphan validation.
SELECT count(*) AS candidate_count FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE e.id='ab000640-fb8e-43ba-850b-c3da076f00b9'::uuid AND o.slug='auditorio-nacional-inaem';
SELECT count(*) AS survivor_count FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE e.id='f6778b5d-1f92-4089-b5cb-1567f47c3da5'::uuid AND o.slug='auditorio-nacional-inaem';
SELECT count(*) AS candidate_dependencies FROM (
 SELECT event_id FROM public.event_sources WHERE event_id='ab000640-fb8e-43ba-850b-c3da076f00b9'::uuid
 UNION ALL SELECT event_id FROM public.event_programme WHERE event_id='ab000640-fb8e-43ba-850b-c3da076f00b9'::uuid
 UNION ALL SELECT event_id FROM public.event_credits WHERE event_id='ab000640-fb8e-43ba-850b-c3da076f00b9'::uuid
 UNION ALL SELECT event_id FROM public.user_event_relations WHERE event_id='ab000640-fb8e-43ba-850b-c3da076f00b9'::uuid
 UNION ALL SELECT event_id FROM public.schedule_events WHERE event_id='ab000640-fb8e-43ba-850b-c3da076f00b9'::uuid
) d;
