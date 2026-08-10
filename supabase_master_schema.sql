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

  preferred_language text not null default 'zh',

  invite_credits integer not null default 2
    check (invite_credits >= 0),

  invite_prefix text not null default 'BYE'
    check (invite_prefix ~ '^[A-Z0-9]{2,10}$'),

  max_subscriptions integer not null default 3,
  daily_update_limit integer not null default 1,

  monthly_character_limit integer not null default 100000,
  used_characters integer not null default 0,

  usage_period_start date not null
    default date_trunc('month', now())::date,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);


-- ==========================================
-- Invitation codes
-- ==========================================

create table if not exists public.invite_codes (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  created_by uuid references public.profiles(id) on delete set null,
  max_uses integer not null check (max_uses > 0),
  used_count integer not null default 0 check (used_count >= 0 and used_count <= max_uses),
  status text not null default 'active' check (status in ('active','exhausted')),
  child_prefix text not null default 'BYE' check (child_prefix ~ '^[A-Z0-9]{2,10}$'),
  created_at timestamptz not null default now()
);

alter table public.invite_codes enable row level security;

insert into public.invite_codes (code, max_uses, used_count, status, child_prefix)
values ('DONTASKME', 10, 0, 'active', 'IDC')
on conflict (code) do update set child_prefix = 'IDC';

create or replace function public.claim_invite_code(p_code text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare claimed boolean;
begin
  update public.invite_codes
  set used_count = used_count + 1,
      status = case when used_count + 1 >= max_uses then 'exhausted' else status end
  where code = upper(trim(p_code)) and status = 'active' and used_count < max_uses
  returning true into claimed;
  return coalesce(claimed, false);
end;
$$;

create or replace function public.create_generated_invite(p_user_id uuid, p_code text)
returns table(code text, remaining_credits integer)
language plpgsql security definer set search_path = '' as $$
declare remaining integer;
begin
  update public.profiles
  set invite_credits = invite_credits - 1, updated_at = now()
  where id = p_user_id and invite_credits > 0
  returning invite_credits into remaining;
  if remaining is null then raise exception 'No invitation credits remaining.'; end if;
  insert into public.invite_codes (code, created_by, max_uses, used_count, status, child_prefix)
  select upper(trim(p_code)), p_user_id, 1, 0, 'active', invite_prefix
  from public.profiles where id = p_user_id;
  return query select upper(trim(p_code)), remaining;
end;
$$;

revoke all on table public.invite_codes from anon, authenticated;
revoke execute on function public.claim_invite_code(text) from public, anon, authenticated;
revoke execute on function public.create_generated_invite(uuid, text) from public, anon, authenticated;
grant execute on function public.claim_invite_code(text) to service_role;
grant execute on function public.create_generated_invite(uuid, text) to service_role;


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

  country text not null default 'other',
  source_type text not null default 'rss',

  language text not null default 'zh',
  mode text not null default 'summary',

  enabled boolean not null default true,

  last_run_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

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

  source text not null default '',
  country text not null default 'other',

  published_at timestamptz,

  language text not null default 'zh',
  mode text not null default 'summary',

  result text not null,

  processed_at timestamptz not null default now(),

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

  characters integer not null default 0,

  created_at timestamptz not null default now()
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
  country text not null default 'other',

  original_title text,
  title text,

  language text not null default 'zh',
  mode text not null default 'summary',

  category text,
  translation_instruction text,

  author text,
  author_label text,

  cover text,

  contents jsonb,

  summaries jsonb,
  translations jsonb,
  translated_titles jsonb,
  titles jsonb,
  translation_jobs jsonb,

  result text,

  raw_data jsonb,

  published boolean not null default true,

  published_at timestamptz,
  processed_at timestamptz,
  metadata_updated_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);


create index if not exists public_articles_country_idx
on public.public_articles(country);


create index if not exists public_articles_category_idx
on public.public_articles(category);


create index if not exists public_articles_published_idx
on public.public_articles(published);


create index if not exists public_articles_published_at_idx
on public.public_articles(published_at desc);


-- ==========================================
-- App state replacement for Blob JSON
-- ==========================================

create table if not exists public.public_app_state (
  key text primary key,

  value jsonb not null,

  updated_at timestamptz not null default now()
);


create table if not exists public.public_seen_urls (
  url text primary key,

  created_at timestamptz not null default now()
);


create table if not exists public.public_scheduled_state (
  key text primary key,

  value jsonb not null,

  updated_at timestamptz not null default now()
);


-- ==========================================
-- New user trigger
-- ==========================================

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin

  insert into public.profiles (id, email, invite_prefix)
  values (
    new.id,
    coalesce(new.email, new.id::text),
    coalesce(nullif(new.raw_user_meta_data->>'invite_prefix', ''), 'BYE')
  )
  on conflict (id) do nothing;

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

alter table public.profiles
enable row level security;

alter table public.user_subscriptions
enable row level security;

alter table public.user_articles
enable row level security;

alter table public.usage_events
enable row level security;

alter table public.public_articles
enable row level security;


-- ==========================================
-- Remove old policies
-- ==========================================

drop policy if exists profiles_select_own
on public.profiles;

drop policy if exists subscriptions_select_own
on public.user_subscriptions;

drop policy if exists articles_select_own
on public.user_articles;

drop policy if exists articles_delete_own
on public.user_articles;

drop policy if exists usage_select_own
on public.usage_events;

drop policy if exists public_articles_read
on public.public_articles;


-- ==========================================
-- User policies
-- ==========================================

create policy profiles_select_own
on public.profiles
for select
to authenticated
using (
  auth.uid() = id
);


create policy subscriptions_select_own
on public.user_subscriptions
for select
to authenticated
using (
  auth.uid() = user_id
);


create policy articles_select_own
on public.user_articles
for select
to authenticated
using (
  auth.uid() = user_id
);


create policy articles_delete_own
on public.user_articles
for delete
to authenticated
using (
  auth.uid() = user_id
);


create policy usage_select_own
on public.usage_events
for select
to authenticated
using (
  auth.uid() = user_id
);


create policy public_articles_read
on public.public_articles
for select
to anon, authenticated
using (
  published = true
);


-- ==========================================
-- Permissions
-- ==========================================

grant usage on schema public
to anon, authenticated;


grant select on public.public_articles
to anon, authenticated;


grant select on public.profiles
to authenticated;


grant select on public.user_subscriptions
to authenticated;


grant select, delete on public.user_articles
to authenticated;


grant select on public.usage_events
to authenticated;
