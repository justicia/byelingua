alter table public.profiles
  add column if not exists preferred_language text not null default 'zh';

alter table public.profiles
  drop constraint if exists profiles_preferred_language_check;

alter table public.profiles
  add constraint profiles_preferred_language_check
  check (preferred_language in ('zh','en','fr','es','de','it','pt','ja'));
