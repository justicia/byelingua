-- Keep visitor-only activities auditable in Events while excluding them from
-- the public performance catalogue.  Ingestion marks them visitor_activity.
create or replace view public.event_catalog_v1 as
select
  e.event_key as event_id,
  es.source,
  es.source_event_id,
  es.source_url,
  o.name as organization,
  v.name as venue,
  e.room,
  e.date,
  e.start_time,
  e.end_time,
  e.timezone,
  e.event_type,
  e.title,
  e.original_title,
  e.status,
  e.ticket_url,
  e.fetched_at,
  e.source_updated_at,
  e.review_status
from public.events e
join public.organizations o on o.id = e.organization_id
join public.venues v on v.id = e.venue_id
join public.event_sources es on es.event_id = e.id
where e.event_type <> 'visitor_activity';
