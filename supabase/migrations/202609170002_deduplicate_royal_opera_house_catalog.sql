create or replace view public.event_catalog_v1 as
with ranked as (
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
    e.review_status,
    row_number() over (
      partition by
        case when v.name = 'Royal Opera House' then e.organization_id::text else e.id::text end,
        case when v.name = 'Royal Opera House' then e.venue_id::text else e.id::text end,
        case when v.name = 'Royal Opera House' then coalesce(e.room, '') else e.id::text end,
        case when v.name = 'Royal Opera House' then e.date::text else e.id::text end,
        case when v.name = 'Royal Opera House' then coalesce(e.start_time::text, '') else e.id::text end,
        case when v.name = 'Royal Opera House' then lower(regexp_replace(trim(e.title), '\s+', ' ', 'g')) else e.id::text end
      order by
        case when es.source_url not like '%/api/events%' then 1 else 0 end desc,
        ((select count(*) from public.event_programme ep where ep.event_id = e.id) +
         (select count(*) from public.event_credits ec where ec.event_id = e.id)) desc,
        e.fetched_at desc nulls last,
        e.id
    ) as catalog_rank
  from public.events e
  join public.organizations o on o.id = e.organization_id
  join public.venues v on v.id = e.venue_id
  join public.event_sources es on es.event_id = e.id
  where e.event_type <> 'visitor_activity'
)
select
  event_id, source, source_event_id, source_url, organization, venue, room,
  date, start_time, end_time, timezone, event_type, title, original_title,
  status, ticket_url, fetched_at, source_updated_at, review_status
from ranked
where catalog_rank = 1;
