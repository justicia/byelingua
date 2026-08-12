-- Schedule lifecycle and per-schedule attendance fields.
-- Safe to run repeatedly after supabase_schedules_migration.sql.
-- This migration intentionally does not touch the event catalog tables.

alter table public.schedules
  add column if not exists confirmed_at timestamptz,
  add column if not exists archived_at timestamptz,
  add column if not exists needs_reconfirmation boolean not null default false;

-- Convert legacy lifecycle values before installing the final constraint.
update public.schedules
set status = 'confirmed', archived_at = coalesce(archived_at, now())
where status = 'archived';

update public.schedules
set status = 'confirmed'
where status in ('planned', 'completed');

update public.schedules
set confirmed_at = coalesce(confirmed_at, updated_at)
where status = 'confirmed';

do $$
declare constraint_name text;
begin
  select conname into constraint_name
  from pg_constraint c
  join pg_class t on t.oid = c.conrelid
  join pg_namespace n on n.oid = t.relnamespace
  where n.nspname = 'public' and t.relname = 'schedules'
    and c.contype = 'c' and pg_get_constraintdef(c.oid) like '%status%';
  if constraint_name is not null then
    execute format('alter table public.schedules drop constraint %I', constraint_name);
  end if;
exception when undefined_table then null;
end $$;

alter table public.schedules
  add constraint schedules_status_check
  check (status in ('draft', 'confirmed'));

alter table public.schedule_events
  add column if not exists intention text not null default 'interested',
  add column if not exists attendance_status text not null default 'pending',
  add column if not exists attended_at timestamptz,
  add column if not exists attendance_updated_at timestamptz,
  add column if not exists event_snapshot jsonb;

alter table public.schedule_events drop constraint if exists schedule_events_intention_check;
alter table public.schedule_events
  add constraint schedule_events_intention_check
  check (intention in ('interested', 'optional', 'must_go'));

alter table public.schedule_events drop constraint if exists schedule_events_attendance_status_check;
alter table public.schedule_events
  add constraint schedule_events_attendance_status_check
  check (attendance_status in ('pending', 'attended', 'missed'));

create index if not exists schedules_user_lifecycle_idx
  on public.schedules (user_id, status, archived_at, updated_at desc);
create index if not exists schedule_events_attendance_idx
  on public.schedule_events (schedule_id, attendance_status);

alter table public.schedules enable row level security;
alter table public.schedule_events enable row level security;
drop policy if exists schedules_owner on public.schedules;
create policy schedules_owner on public.schedules for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists schedule_events_owner on public.schedule_events;
create policy schedule_events_owner on public.schedule_events for all to authenticated
  using (exists (select 1 from public.schedules s where s.id = schedule_id and s.user_id = auth.uid()))
  with check (exists (select 1 from public.schedules s where s.id = schedule_id and s.user_id = auth.uid()));

