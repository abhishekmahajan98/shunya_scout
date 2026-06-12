-- Shunya Scout: run once in the Supabase SQL editor.
-- Create a public Storage bucket named "reports" (or set SUPABASE_STORAGE_BUCKET).
-- The backend uses the publishable (anon) key server-side only; RLS policies below allow those operations.

create table if not exists public.match_reports (
  id uuid primary key default gen_random_uuid(),
  report_date date not null,
  team_a text not null,
  team_b text not null,
  pdf_slug text not null,
  markdown text,
  raw_scout_data text,
  storage_path text not null,
  quick_test boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (report_date, pdf_slug)
);

create index if not exists idx_match_reports_report_date
  on public.match_reports (report_date desc);

create or replace function public.set_match_reports_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_match_reports_updated_at on public.match_reports;
create trigger trg_match_reports_updated_at
before update on public.match_reports
for each row execute function public.set_match_reports_updated_at();

-- Row Level Security (required when using the publishable/anon key)
alter table public.match_reports enable row level security;

drop policy if exists "anon_select_match_reports" on public.match_reports;
create policy "anon_select_match_reports"
  on public.match_reports for select
  to anon
  using (true);

drop policy if exists "anon_insert_match_reports" on public.match_reports;
create policy "anon_insert_match_reports"
  on public.match_reports for insert
  to anon
  with check (true);

drop policy if exists "anon_update_match_reports" on public.match_reports;
create policy "anon_update_match_reports"
  on public.match_reports for update
  to anon
  using (true);

drop policy if exists "anon_delete_match_reports" on public.match_reports;
create policy "anon_delete_match_reports"
  on public.match_reports for delete
  to anon
  using (true);

-- Storage policies for the "reports" bucket
drop policy if exists "anon_read_reports_bucket" on storage.objects;
create policy "anon_read_reports_bucket"
  on storage.objects for select
  to anon
  using (bucket_id = 'reports');

drop policy if exists "anon_insert_reports_bucket" on storage.objects;
create policy "anon_insert_reports_bucket"
  on storage.objects for insert
  to anon
  with check (bucket_id = 'reports');

drop policy if exists "anon_update_reports_bucket" on storage.objects;
create policy "anon_update_reports_bucket"
  on storage.objects for update
  to anon
  using (bucket_id = 'reports');

drop policy if exists "anon_delete_reports_bucket" on storage.objects;
create policy "anon_delete_reports_bucket"
  on storage.objects for delete
  to anon
  using (bucket_id = 'reports');
