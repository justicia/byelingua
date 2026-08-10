alter table public.profiles
  add column if not exists invite_credits integer not null default 2
  check (invite_credits >= 0);

alter table public.profiles
  add column if not exists invite_prefix text not null default 'BYE'
  check (invite_prefix ~ '^[A-Z0-9]{2,10}$');

create table if not exists public.invite_codes (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  created_by uuid references public.profiles(id) on delete set null,
  max_uses integer not null check (max_uses > 0),
  used_count integer not null default 0 check (used_count >= 0 and used_count <= max_uses),
  status text not null default 'active' check (status in ('active', 'exhausted')),
  child_prefix text not null default 'BYE' check (child_prefix ~ '^[A-Z0-9]{2,10}$'),
  created_at timestamptz not null default now()
);

alter table public.invite_codes
  add column if not exists child_prefix text not null default 'BYE'
  check (child_prefix ~ '^[A-Z0-9]{2,10}$');

alter table public.invite_codes enable row level security;

insert into public.invite_codes (code, max_uses, used_count, status, child_prefix)
values ('DONTASKME', 10, 0, 'active', 'IDC')
on conflict (code) do update set child_prefix = 'IDC';

update public.invite_codes
set child_prefix = case code
  when 'MCFISHTHEBEST' then 'MCF'
  when 'BLUEMONDAY' then 'BLUE'
  when 'BWW964' then 'BWW'
  else child_prefix
end
where code in ('MCFISHTHEBEST', 'BLUEMONDAY', 'BWW964');

create or replace function public.claim_invite_code(p_code text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  claimed boolean;
begin
  update public.invite_codes
  set
    used_count = used_count + 1,
    status = case when used_count + 1 >= max_uses then 'exhausted' else status end
  where code = upper(trim(p_code))
    and status = 'active'
    and used_count < max_uses
  returning true into claimed;

  return coalesce(claimed, false);
end;
$$;

create or replace function public.create_generated_invite(p_user_id uuid, p_code text)
returns table(code text, remaining_credits integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
  remaining integer;
begin
  update public.profiles
  set invite_credits = invite_credits - 1,
      updated_at = now()
  where id = p_user_id
    and invite_credits > 0
  returning invite_credits into remaining;

  if remaining is null then
    raise exception 'No invitation credits remaining.';
  end if;

  insert into public.invite_codes (code, created_by, max_uses, used_count, status, child_prefix)
  select upper(trim(p_code)), p_user_id, 1, 0, 'active', invite_prefix
  from public.profiles where id = p_user_id;

  return query select upper(trim(p_code)), remaining;
end;
$$;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, email, invite_prefix)
  values (new.id, coalesce(new.email, new.id::text), coalesce(nullif(new.raw_user_meta_data->>'invite_prefix', ''), 'BYE'))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();

revoke all on table public.invite_codes from anon, authenticated;
revoke execute on function public.claim_invite_code(text) from public, anon, authenticated;
revoke execute on function public.create_generated_invite(uuid, text) from public, anon, authenticated;
grant execute on function public.claim_invite_code(text) to service_role;
grant execute on function public.create_generated_invite(uuid, text) to service_role;
