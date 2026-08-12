-- Persistent user-owned schedules. A saved Schedule is the editable list;
-- Generate Schedule remains a view/operation over that list.
create table if not exists public.schedules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (length(trim(title)) > 0),
  status text not null default 'draft'
    check (status in ('draft', 'planned', 'completed', 'archived')),
  start_date date null,
  end_date date null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.schedule_events (
  id uuid primary key default gen_random_uuid(),
  schedule_id uuid not null references public.schedules(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  sort_order integer not null default 0,
  note text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (schedule_id, event_id)
);

create index if not exists schedules_user_status_idx
  on public.schedules (user_id, status, updated_at desc);
create index if not exists schedule_events_schedule_order_idx
  on public.schedule_events (schedule_id, sort_order, created_at);
create index if not exists schedule_events_event_idx
  on public.schedule_events (event_id);

alter table public.schedules enable row level security;
alter table public.schedule_events enable row level security;

drop policy if exists schedules_owner on public.schedules;
create policy schedules_owner on public.schedules
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists schedule_events_owner on public.schedule_events;
create policy schedule_events_owner on public.schedule_events
  for all using (
    exists (select 1 from public.schedules s where s.id = schedule_id and s.user_id = auth.uid())
  ) with check (
    exists (select 1 from public.schedules s where s.id = schedule_id and s.user_id = auth.uid())
  );

comment on table public.schedules is 'Persistent user-owned event lists; generated itineraries are views over schedules.';
comment on table public.schedule_events is 'Schedule membership, independent from user_event_relations intent status.';
