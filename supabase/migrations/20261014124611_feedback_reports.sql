-- Feedback is written only by the Vercel server with the Supabase secret key.
-- Do not grant browser roles direct access to reports or submitter email addresses.
create table if not exists public.feedback_reports (
  id uuid primary key default gen_random_uuid(),
  category text not null check (category in ('incorrect_event', 'site_problem', 'suggestion', 'other')),
  message text not null check (char_length(message) between 10 and 4000),
  email text,
  page_path text not null default '/',
  event_id text,
  event_title text,
  event_date text,
  event_venue text,
  source_url text,
  schedule_id text,
  language text,
  user_agent text,
  request_fingerprint text not null,
  status text not null default 'new' check (status in ('new', 'reviewing', 'resolved', 'rejected')),
  notification_status text not null default 'pending' check (notification_status in ('pending', 'sent', 'failed', 'skipped')),
  notification_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);

alter table public.feedback_reports enable row level security;

revoke all on table public.feedback_reports from anon, authenticated;
grant select, insert, update, delete on table public.feedback_reports to service_role;

create index if not exists feedback_reports_status_created_idx
  on public.feedback_reports (status, created_at desc);
create index if not exists feedback_reports_fingerprint_created_idx
  on public.feedback_reports (request_fingerprint, created_at desc);
