-- ==========================================
-- Byelingua Supabase Master Schema
-- ==========================================

create extension if not exists pgcrypto;


-- ==========================================
-- User profiles
-- ==========================================

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,

  plan text not null default 'trial'
    check (plan in ('trial','basic','pro')),

  status text not null default 'active'
    check (status in ('active','paused','cancelled')),

  max_subscriptions integer not null default 3,
  daily_update_limit integer not null default 1,

  monthly_character_limit integer not null default 100000,
  used_characters integer not null default 0,

  usage_period_start date not null default date_trunc('month', now())::date,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);



-- ==========================================
-- User subscriptions
-- ==========================================

create table if not exists public.user_subscriptions (

  id uuid primary key default gen_random_uuid(),

  user_id uuid not null
    references public.profiles(id)
    on delete cascade,

  name text not null,

  url text not null,

  feed_url text not null,

  country text default 'other',

  source_type text default 'rss',

  language text default 'zh',

  mode text default 'summary',

  enabled boolean default true,

  last_run_at timestamptz,

  created_at timestamptz default now(),

  updated_at timestamptz default now(),

  unique(user_id, feed_url)

);



-- ==========================================
-- User generated articles
-- ==========================================

create table if not exists public.user_articles (

  id uuid primary key default gen_random_uuid(),

  user_id uuid not null
    references public.profiles(id)
    on delete cascade,

  subscription_id uuid
    references public.user_subscriptions(id)
    on delete set null,

  canonical_url text not null,

  title text not null,

  source text default '',

  country text default 'other',

  published_at timestamptz,

  language text default 'zh',

  mode text default 'summary',

  result text,

  processed_at timestamptz default now(),

  unique(user_id, canonical_url, language)

);



-- ==========================================
-- Usage tracking
-- ==========================================

create table if not exists public.usage_events (

  id bigint generated always as identity primary key,

  user_id uuid not null
    references public.profiles(id)
    on delete cascade,

  event_type text not null,

  characters integer default 0,

  created_at timestamptz default now()

);



-- ==========================================
-- Public article database
-- ==========================================

create table if not exists public.public_articles (

  id text primary key,

  canonical_url text unique not null,

  url text not null,

  kind text,

  source text,

  country text default 'other',

  original_title text,

  title text,

  language text default 'zh',

  mode text default 'summary',

  category text,

  author text,

  cover text,

  contents text,

  summaries jsonb,

  translations jsonb,

  translation_jobs jsonb,

  published boolean default true,

  published_at timestamptz,

  processed_at timestamptz,

  created_at timestamptz default now(),

  updated_at timestamptz default now()

);



create index if not exists public_articles_country_idx
on public.public_articles(country);


create index if not exists public_articles_category_idx
on public.public_articles(category);


create index if not exists public_articles_published_idx
on public.public_articles(published);



-- ==========================================
-- App state replacement for Blob json
-- ==========================================

create table if not exists public.public_app_state (

  key text primary key,

  value jsonb not null,

  updated_at timestamptz default now()

);



create table if not exists public.public_seen_urls (

  url text primary key,

  created_at timestamptz default now()

);



create table if not exists public.public_scheduled_state (

  key text primary key,

  value jsonb not null,

  updated_at timestamptz default now()

);



-- ==========================================
-- New user trigger
-- ==========================================

create or replace function public.handle_new_user()

returns trigger

language plpgsql

security definer set search_path = ''

as $$

begin

insert into public.profiles(id,email)

values(
new.id,
coalesce(new.email,new.id::text)
)

on conflict(id) do nothing;


return new;

end;

$$;



drop trigger if exists on_auth_user_created
on auth.users;


create trigger on_auth_user_created

after insert on auth.users

for each row

execute procedure public.handle_new_user();



-- ==========================================
-- Row Level Security
-- ==========================================

alter table public.profiles enable row level security;

alter table public.user_subscriptions enable row level security;

alter table public.user_articles enable row level security;

alter table public.usage_events enable row level security;

alter table public.public_articles enable row level security;



-- remove old policies

drop policy if exists profiles_select_own
on public.profiles;


drop policy if exists public_articles_read
on public.public_articles;



-- user policies

create policy profiles_select_own

on public.profiles

for select

to authenticated

using(auth.uid() = id);



create policy public_articles_read

on public.public_articles

for select

to anon, authenticated

using(published=true);



-- permissions

grant usage on schema public to anon, authenticated;


grant select on public.public_articles
to anon, authenticated;


grant select on public.profiles
to authenticated;


grant select on public.user_articles
to authenticated;


grant select on public.user_subscriptions
to authenticated;