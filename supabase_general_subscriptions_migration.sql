-- Optional public/general source preferences. Personal My subscriptions remain
-- in user_subscriptions and keep the existing maximum-three rule.
create table if not exists public.user_general_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_id text not null,
  feed_url text,
  name text,
  enabled boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, source_id)
);
alter table public.user_general_subscriptions enable row level security;
drop policy if exists user_general_subscriptions_owner on public.user_general_subscriptions;
create policy user_general_subscriptions_owner on public.user_general_subscriptions
  for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
grant select, insert, update, delete on public.user_general_subscriptions to authenticated;
