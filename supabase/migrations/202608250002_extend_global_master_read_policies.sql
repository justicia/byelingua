-- Global Master read-only visibility for the Cloud Pipeline snapshot.
-- Executed once in the approved final-unblock task; retain as migration history.
alter table public.artists enable row level security;
alter table public.artist_aliases enable row level security;
alter table public.characters enable row level security;
alter table public.character_aliases enable row level security;
alter table public.work_characters enable row level security;

drop policy if exists artists_public_read on public.artists;
create policy artists_public_read on public.artists for select to anon, authenticated using (true);

drop policy if exists artist_aliases_public_read on public.artist_aliases;
create policy artist_aliases_public_read on public.artist_aliases for select to anon, authenticated using (true);

drop policy if exists characters_public_read on public.characters;
create policy characters_public_read on public.characters for select to anon, authenticated using (true);

drop policy if exists character_aliases_public_read on public.character_aliases;
create policy character_aliases_public_read on public.character_aliases for select to anon, authenticated using (true);

drop policy if exists work_characters_public_read on public.work_characters;
create policy work_characters_public_read on public.work_characters for select to anon, authenticated using (true);

