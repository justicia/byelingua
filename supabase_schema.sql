create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  plan text not null default 'trial' check (plan in ('trial', 'basic', 'pro')),
  status text not null default 'active' check (status in ('active', 'paused', 'cancelled')),
  max_subscriptions integer not null default 3 check (max_subscriptions >= 0),
  daily_update_limit integer not null default 1 check (daily_update_limit >= 0),
  monthly_character_limit integer not null default 100000 check (monthly_character_limit >= 0),
  used_characters integer not null default 0 check (used_characters >= 0),
  usage_period_start date not null default date_trunc('month', now())::date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  url text not null,
  feed_url text not null,
  country text not null default 'other',
  source_type text not null default 'rss' check (source_type in ('rss', 'website')),
  language text not null default 'zh',
  mode text not null default 'summary' check (mode in ('summary', 'translate')),
  enabled boolean not null default true,
  last_run_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, feed_url)
);

create table if not exists public.user_articles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  subscription_id uuid references public.user_subscriptions(id) on delete set null,
  canonical_url text not null,
  title text not null,
  source text not null default '',
  country text not null default 'other',
  published_at timestamptz,
  language text not null default 'zh',
  mode text not null default 'summary' check (mode in ('summary', 'translate')),
  result text not null,
  processed_at timestamptz not null default now(),
  unique (user_id, canonical_url, language)
);

create table if not exists public.usage_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  event_type text not null check (event_type in ('digest', 'summary', 'translation')),
  characters integer not null default 0 check (characters >= 0),
  created_at timestamptz not null default now()
);

create index if not exists user_subscriptions_user_id_idx on public.user_subscriptions(user_id);
create index if not exists user_articles_user_id_idx on public.user_articles(user_id);
create index if not exists user_articles_subscription_id_idx on public.user_articles(subscription_id);
create index if not exists usage_events_user_id_created_at_idx on public.usage_events(user_id, created_at);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, coalesce(new.email, new.id::text))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.user_subscriptions enable row level security;
alter table public.user_articles enable row level security;
alter table public.usage_events enable row level security;

create policy "profiles_select_own" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "subscriptions_select_own" on public.user_subscriptions
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "articles_select_own" on public.user_articles
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "articles_delete_own" on public.user_articles
  for delete to authenticated using ((select auth.uid()) = user_id);
create policy "usage_select_own" on public.usage_events
  for select to authenticated using ((select auth.uid()) = user_id);

grant usage on schema public to authenticated;
grant select on public.profiles to authenticated;
grant select on public.user_subscriptions to authenticated;
grant select, delete on public.user_articles to authenticated;
grant select on public.usage_events to authenticated;
