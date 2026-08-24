-- Public read access for canonical Global Master metadata used by read-only ingestion.
-- No INSERT, UPDATE, or DELETE policies are created.
alter table public.composers enable row level security;
alter table public.composer_aliases enable row level security;
alter table public.works enable row level security;

drop policy if exists composers_public_read on public.composers;
create policy composers_public_read
  on public.composers
  for select
  to anon, authenticated
  using (true);

drop policy if exists composer_aliases_public_read on public.composer_aliases;
create policy composer_aliases_public_read
  on public.composer_aliases
  for select
  to anon, authenticated
  using (true);

drop policy if exists works_public_read on public.works;
create policy works_public_read
  on public.works
  for select
  to anon, authenticated
  using (true);
