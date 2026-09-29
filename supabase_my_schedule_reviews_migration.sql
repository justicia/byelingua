-- Personal performance timeline and user review foundation.
-- This migration extends user_event_relations without changing the existing
-- Schedule Builder intent semantics used by Trips / saved schedules.

alter table public.user_event_relations
  add column if not exists personal_status text null
    check (personal_status is null or personal_status in ('want_to_go', 'going', 'attended', 'not_attended'));

update public.user_event_relations
set personal_status = case
  when attendance_status = 'attended' then 'attended'
  when attendance_status = 'missed' then 'not_attended'
  when intent_status = 'must_go' then 'going'
  else 'want_to_go'
end
where personal_status is null;

create index if not exists user_event_relations_user_personal_status_idx
  on public.user_event_relations (user_id, personal_status, updated_at desc);

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

alter table public.event_reviews
  add column if not exists overall_rating integer null
    check (overall_rating is null or overall_rating between 1 and 5),
  add column if not exists final_score numeric(2,1) null
    check (final_score is null or (final_score >= 1 and final_score <= 5)),
  add column if not exists comment text null,
  add column if not exists identity_mode text not null default 'anonymous'
    check (identity_mode in ('anonymous', 'public'));

update public.event_reviews
set overall_rating = coalesce(overall_rating, rating),
    comment = coalesce(comment, review_text)
where overall_rating is null or comment is null;

create unique index if not exists event_reviews_user_event_unique_idx
  on public.event_reviews (user_id, event_id);
create index if not exists event_reviews_event_public_idx
  on public.event_reviews (event_id, visibility, updated_at desc);

create table if not exists public.user_event_component_ratings (
  id uuid primary key default gen_random_uuid(),
  review_id uuid not null references public.event_reviews(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  component_type text not null
    check (component_type in ('conductor', 'soloist', 'orchestra', 'stage')),
  event_credit_id uuid null references public.event_credits(id) on delete cascade,
  artist_id uuid null references public.artists(id) on delete cascade,
  rating integer not null check (rating between 1 and 5),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (component_type = 'stage' and event_credit_id is null and artist_id is null)
    or
    (component_type <> 'stage' and event_credit_id is not null and artist_id is not null)
  )
);

create unique index if not exists user_event_component_ratings_credit_unique_idx
  on public.user_event_component_ratings (review_id, component_type, event_credit_id)
  where event_credit_id is not null;
create unique index if not exists user_event_component_ratings_stage_unique_idx
  on public.user_event_component_ratings (review_id, component_type)
  where component_type = 'stage';
create index if not exists user_event_component_ratings_artist_idx
  on public.user_event_component_ratings (artist_id, event_id, updated_at desc)
  where artist_id is not null;
create index if not exists user_event_component_ratings_event_idx
  on public.user_event_component_ratings (event_id, component_type, updated_at desc);

alter table public.event_reviews enable row level security;
alter table public.user_event_component_ratings enable row level security;

-- Owner-only direct Data API access. Public review presentation is intentionally
-- served through the application API so anonymous reviews never expose user_id.
drop policy if exists event_reviews_owner on public.event_reviews;
drop policy if exists event_reviews_select_own on public.event_reviews;
drop policy if exists event_reviews_insert_own on public.event_reviews;
drop policy if exists event_reviews_update_own on public.event_reviews;
drop policy if exists event_reviews_delete_own on public.event_reviews;

create policy event_reviews_select_own on public.event_reviews
  for select to authenticated
  using ((select auth.uid()) = user_id);
create policy event_reviews_insert_own on public.event_reviews
  for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy event_reviews_update_own on public.event_reviews
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy event_reviews_delete_own on public.event_reviews
  for delete to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists user_event_component_ratings_select_own on public.user_event_component_ratings;
drop policy if exists user_event_component_ratings_insert_own on public.user_event_component_ratings;
drop policy if exists user_event_component_ratings_update_own on public.user_event_component_ratings;
drop policy if exists user_event_component_ratings_delete_own on public.user_event_component_ratings;

create policy user_event_component_ratings_select_own on public.user_event_component_ratings
  for select to authenticated
  using ((select auth.uid()) = user_id);
create policy user_event_component_ratings_insert_own on public.user_event_component_ratings
  for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy user_event_component_ratings_update_own on public.user_event_component_ratings
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy user_event_component_ratings_delete_own on public.user_event_component_ratings
  for delete to authenticated
  using ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.event_reviews to authenticated;
grant select, insert, update, delete on public.user_event_component_ratings to authenticated;
grant select, update on public.user_event_relations to authenticated;

comment on column public.user_event_relations.personal_status is
  'Private My Schedule state: want_to_go, going, attended, or not_attended. Independent from Trip intent_status.';
comment on table public.event_reviews is
  'One user review per dated performance. Public presentation is sanitized by the application API.';
comment on table public.user_event_component_ratings is
  'Performance-specific five-star ratings for conductor, soloists/cast, orchestra/ensemble, and stage.';
