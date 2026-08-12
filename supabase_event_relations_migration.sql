-- Event planning relationships and future review storage.
create table if not exists public.user_event_relations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  intent_status text not null default 'interested'
    check (intent_status in ('interested', 'maybe_go', 'must_go')),
  is_planned boolean not null default true,
  attendance_status text null
    check (attendance_status is null or attendance_status in ('planned', 'attended', 'missed')),
  ticket_status text null
    check (ticket_status is null or ticket_status in ('unknown', 'need_ticket', 'booked')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, event_id)
);

create index if not exists user_event_relations_user_intent_idx
  on public.user_event_relations (user_id, intent_status);

alter table public.user_event_relations add column if not exists is_planned boolean not null default true;

create table if not exists public.event_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  rating integer null check (rating is null or rating between 1 and 5),
  review_text text null,
  visibility text not null default 'private' check (visibility in ('private', 'public')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists event_reviews_user_event_idx
  on public.event_reviews (user_id, event_id);

alter table public.user_event_relations enable row level security;
alter table public.event_reviews enable row level security;

drop policy if exists user_event_relations_owner on public.user_event_relations;
create policy user_event_relations_owner on public.user_event_relations
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists event_reviews_owner on public.event_reviews;
create policy event_reviews_owner on public.event_reviews
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
