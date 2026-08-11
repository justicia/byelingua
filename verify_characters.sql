-- Run after supabase_characters_migration.sql and the character-aware reimport.
select canonical_name, w.title as work_title, w.composer
from public.work_characters wc
join public.works w on w.id = wc.work_id
where lower(canonical_name) in ('rosina', 'figaro', 'kundry', 'wotan')
order by canonical_name, work_title;

select event_id, date, start_time, organization, venue, work_title,
       canonical_name, artist_name
from public.event_character_catalog_v1
where lower(canonical_name) in ('rosina', 'figaro', 'kundry', 'wotan')
order by date, start_time;
