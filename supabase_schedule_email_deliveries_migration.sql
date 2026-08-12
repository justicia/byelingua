-- Durable audit trail for user-owned Schedule email deliveries.
-- Safe to run repeatedly after supabase_schedules_migration.sql.
create table if not exists public.schedule_email_deliveries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  schedule_id uuid not null references public.schedules(id) on delete cascade,
  recipient_email text not null,
  status text not null default 'pending' check (status in ('pending','sent','failed')),
  provider_message_id text null,
  error text null,
  content_hash text null,
  created_at timestamptz not null default now(),
  sent_at timestamptz null
);

create index if not exists schedule_email_deliveries_owner_idx
  on public.schedule_email_deliveries (user_id, created_at desc);
create index if not exists schedule_email_deliveries_schedule_idx
  on public.schedule_email_deliveries (schedule_id, created_at desc);

alter table public.schedule_email_deliveries enable row level security;
drop policy if exists schedule_email_deliveries_owner on public.schedule_email_deliveries;
create policy schedule_email_deliveries_owner
  on public.schedule_email_deliveries for select to authenticated
  using (auth.uid() = user_id);

revoke all on public.schedule_email_deliveries from anon, authenticated;
grant select on public.schedule_email_deliveries to authenticated;
