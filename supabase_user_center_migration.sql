-- Private User Center foundation. Safe to run after the existing master,
-- event-relations, and schedules migrations.
alter table public.profiles
  add column if not exists display_name text null,
  add column if not exists avatar_url text null,
  add column if not exists email_subscription_enabled boolean not null default true;

alter table public.profiles enable row level security;
alter table public.user_subscriptions enable row level security;

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles
  for update to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

drop policy if exists subscriptions_insert_own on public.user_subscriptions;
create policy subscriptions_insert_own on public.user_subscriptions
  for insert to authenticated
  with check (auth.uid() = user_id);

drop policy if exists subscriptions_update_own on public.user_subscriptions;
create policy subscriptions_update_own on public.user_subscriptions
  for update to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists subscriptions_delete_own on public.user_subscriptions;
create policy subscriptions_delete_own on public.user_subscriptions
  for delete to authenticated
  using (auth.uid() = user_id);

grant update on public.profiles to authenticated;
grant insert, update, delete on public.user_subscriptions to authenticated;

comment on column public.profiles.display_name is 'Reserved for future private/public profile presentation; not required or shown by the current User Center.';
comment on column public.profiles.avatar_url is 'Reserved for future profile media; no upload flow is implemented.';
comment on column public.profiles.email_subscription_enabled is 'Whether the authenticated user wants personalised news email delivery.';
