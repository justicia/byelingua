-- Accent-insensitive entity search without changing canonical/display names.
create extension if not exists unaccent;
create extension if not exists pg_trgm;

create or replace function public.search_key(value text)
returns text
language sql
immutable
parallel safe
as $$
  select trim(regexp_replace(lower(unaccent(coalesce(value, ''))), '\s+', ' ', 'g'));
$$;

create index if not exists artists_search_key_trgm_idx
  on public.artists using gin (public.search_key(artist_name) gin_trgm_ops);
create index if not exists works_title_search_key_trgm_idx
  on public.works using gin (public.search_key(title) gin_trgm_ops);
create index if not exists works_composer_search_key_trgm_idx
  on public.works using gin (public.search_key(composer) gin_trgm_ops);
create index if not exists work_characters_search_key_trgm_idx
  on public.work_characters using gin (public.search_key(canonical_name) gin_trgm_ops);
create index if not exists character_aliases_search_key_trgm_idx
  on public.character_aliases using gin (public.search_key(alias) gin_trgm_ops);
