-- Minimal work-scoped character normalization. Common Event Schema v1.0 is unchanged.
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

-- Deterministic MVP backfill for the current Wiener cast sample.
insert into public.work_characters (work_id, canonical_name)
select distinct ep.work_id,
  case
    when lower(w.title) like 'il barbiere di siviglia%' and lower(ec.raw_character) = 'rosina' then 'Rosina'
    when lower(w.title) like 'il barbiere di siviglia%' and lower(ec.raw_character) = 'figaro' then 'Figaro'
    when lower(w.title) like 'il barbiere di siviglia%' and lower(ec.raw_character) in ('graf almaviva','count almaviva','conte almaviva','almaviva') then 'Conte d’Almaviva'
    when lower(w.title) like 'le nozze di figaro%' and lower(ec.raw_character) = 'figaro' then 'Figaro'
    when lower(w.title) like 'le nozze di figaro%' and lower(ec.raw_character) in ('graf almaviva','count almaviva','conte almaviva','almaviva') then 'Conte d’Almaviva'
    when lower(w.title) = 'parsifal' and lower(ec.raw_character) = 'kundry' then 'Kundry'
    else null
  end
from public.event_credits ec
join public.events e on e.id = ec.event_id
join public.event_programme ep on ep.event_id = e.id and ep."order" = 1
join public.works w on w.id = ep.work_id
where ec.raw_character is not null and (
  (lower(w.title) like 'il barbiere di siviglia%' and lower(ec.raw_character) in ('rosina','figaro','graf almaviva','count almaviva','conte almaviva','almaviva'))
  or (lower(w.title) like 'le nozze di figaro%' and lower(ec.raw_character) in ('figaro','graf almaviva','count almaviva','conte almaviva','almaviva'))
  or (lower(w.title) = 'parsifal' and lower(ec.raw_character) = 'kundry')
)
on conflict (work_id, canonical_name) do nothing;

update public.event_credits ec set character_id = wc.id
from public.events e join public.event_programme ep on ep.event_id = e.id and ep."order" = 1
join public.works w on w.id = ep.work_id
join public.work_characters wc on wc.work_id = ep.work_id
where ec.event_id = e.id and (
  (lower(w.title) like 'il barbiere di siviglia%' and lower(ec.raw_character) = lower(wc.canonical_name))
  or (lower(w.title) like 'le nozze di figaro%' and lower(ec.raw_character) = lower(wc.canonical_name))
  or (lower(w.title) = 'parsifal' and lower(ec.raw_character) = lower(wc.canonical_name))
);
insert into public.character_aliases (character_id, alias, language, source)
select wc.id, alias_name, null, 'wiener_staatsoper'
from public.work_characters wc
join public.works w on w.id = wc.work_id
cross join (values ('Graf Almaviva'), ('Count Almaviva'), ('Almaviva')) aliases(alias_name)
where wc.canonical_name = 'Conte d’Almaviva'
  and lower(w.title) in ('il barbiere di siviglia', 'le nozze di figaro')
on conflict do nothing;
update public.events e set review_status = 'needs_review'
where exists (
  select 1 from public.event_credits ec
  where ec.event_id = e.id and ec.raw_character is not null and ec.character_id is null
);
