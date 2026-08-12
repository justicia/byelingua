-- Work search aliases. The existing public.works.title remains the
-- original-language canonical display title; aliases are search metadata only.
create table if not exists public.work_aliases (
  id uuid primary key default gen_random_uuid(),
  work_id uuid not null references public.works(id) on delete cascade,
  alias text not null,
  language text null,
  source text null,
  created_at timestamptz not null default now(),
  unique (work_id, alias)
);
create index if not exists work_aliases_alias_idx on public.work_aliases (lower(alias));
alter table public.work_aliases enable row level security;
drop policy if exists work_aliases_public_read on public.work_aliases;
create policy work_aliases_public_read on public.work_aliases for select to anon, authenticated using (true);
grant select on public.work_aliases to anon, authenticated;
