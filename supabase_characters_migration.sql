-- Character storage migration only. Do not backfill character_id in this step.
create table if not exists public.work_characters (
  id uuid primary key default gen_random_uuid(),
  work_id uuid not null references public.works(id) on delete cascade,
  canonical_name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (work_id, canonical_name)
);
create table if not exists public.character_aliases (
  id uuid primary key default gen_random_uuid(),
  character_id uuid not null references public.work_characters(id) on delete cascade,
  alias text not null, language text, source text,
  unique (character_id, alias, language, source)
);
alter table public.event_credits add column if not exists character_id uuid references public.work_characters(id);
alter table public.event_credits add column if not exists raw_character text;
update public.event_credits set raw_character = character where raw_character is null and character is not null;
create index if not exists work_characters_name_idx on public.work_characters(canonical_name);
create index if not exists character_aliases_alias_idx on public.character_aliases(alias);
create index if not exists event_credits_character_idx on public.event_credits(character_id);
create or replace view public.event_character_catalog_v1 as
select e.event_key as event_id, e.title, e.date, e.start_time, o.name as organization, v.name as venue,
  w.title as work_title, w.composer, wc.id as character_id, wc.canonical_name,
  ec.raw_character, a.artist_name, ec.role, ec.character
from public.event_credits ec
join public.events e on e.id = ec.event_id
join public.organizations o on o.id = e.organization_id
join public.venues v on v.id = e.venue_id
join public.artists a on a.id = ec.artist_id
left join public.work_characters wc on wc.id = ec.character_id
left join public.event_programme ep on ep.event_id = e.id and ep."order" = 1
left join public.works w on w.id = ep.work_id;
