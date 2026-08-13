-- Daily personal news digest delivery. Safe to run repeatedly.
-- The legacy email_subscription_enabled column is retained for compatibility.

alter table public.profiles
  add column if not exists email_digest_enabled boolean not null default false;

-- Preserve an existing opt-in when the legacy column is present; never turn a
-- canonical true value off during a repeated migration.
do $migration$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'profiles'
      and column_name = 'email_subscription_enabled'
  ) then
    execute $sql$update public.profiles
      set email_digest_enabled = true
      where email_subscription_enabled is true
        and email_digest_enabled is not true$sql$;
  end if;
end $migration$;

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
drop policy if exists email_digest_deliveries_select_own on public.email_digest_deliveries;
create policy email_digest_deliveries_select_own
  on public.email_digest_deliveries for select to authenticated
  using (auth.uid() = user_id);

revoke all on public.email_digest_deliveries from anon;
revoke insert, update, delete on public.email_digest_deliveries from authenticated;
grant select on public.email_digest_deliveries to authenticated;
