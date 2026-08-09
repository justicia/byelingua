-- Byelingua daily personal email digests.
-- Safe to run more than once in the Supabase SQL editor.

alter table public.profiles
  add column if not exists email_digest_enabled boolean not null default false;

create table if not exists public.email_digest_deliveries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  digest_date date not null,
  status text not null default 'pending'
    check (status in ('pending','sent','failed')),
  article_ids uuid[] not null default '{}',
  provider_message_id text,
  error text,
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  unique(user_id, digest_date)
);

alter table public.email_digest_deliveries enable row level security;

drop policy if exists email_digest_deliveries_select_own
  on public.email_digest_deliveries;

create policy email_digest_deliveries_select_own
on public.email_digest_deliveries
for select
to authenticated
using (auth.uid() = user_id);

revoke all on public.email_digest_deliveries from anon;
revoke insert, update, delete on public.email_digest_deliveries from authenticated;
grant select on public.email_digest_deliveries to authenticated;
