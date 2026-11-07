-- BẢN WEB DASHBOARD CHO NHÂN VIÊN. Chạy MỘT LẦN trong Supabase: SQL Editor -> New query -> dán toàn bộ -> Run.
-- Chạy SAU supabase/schema.sql (đã có bảng viewers, reports, hàm is_viewer).
-- Nguyên tắc: mặc định đóng. Chỉ email nằm trong bảng `staff` đọc được dữ liệu; nhân viên chỉ SỬA được vài cột của `drafts`
-- và THÊM được phản hồi. Máy chủ chính (service_role, chạy trên máy chủ dự án) mới được ghi plans/topics/source_runs/reports_internal.

-- 1) Nhân viên
create table if not exists public.staff (
  email      text primary key,
  name       text,
  created_at timestamptz not null default now()
);
alter table public.staff enable row level security;   -- không có policy: nhân viên không đọc được danh sách này

-- Mọi tài khoản đăng nhập hợp lệ (không ẩn danh, chưa bị xóa/chặn) = nhân viên. Xem supabase/staff_any_user.sql.
create or replace function public.is_staff()
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select exists (
    select 1
    from auth.users u
    where u.id = auth.uid()
      and coalesce(u.is_anonymous, false) = false
      and u.deleted_at is null
      and (u.banned_until is null or u.banned_until < now())
  );
$$;
revoke all on function public.is_staff() from public, anon;
grant execute on function public.is_staff() to authenticated;

-- nhân viên cũng đọc được báo cáo đã lược bỏ (bảng reports của người xem ngoài)
drop policy if exists "viewers can read reports" on public.reports;
create policy "viewers can read reports" on public.reports for select to authenticated
  using (public.is_viewer() or public.is_staff());

-- 2) Ghi nhận ai sửa, lúc nào (tự động; máy chủ chính không có email nên ghi 'local')
create or replace function public.set_audit()
returns trigger language plpgsql set search_path = ''
as $$
begin
  new.updated_at := now();
  new.updated_by := coalesce(nullif(auth.jwt() ->> 'email', ''), 'local');
  return new;
end $$;

-- 3) Bài nháp (đồng bộ hai chiều)
create table if not exists public.drafts (
  id           text primary key,
  date         date not null,
  slot         text not null,
  type         text not null default 'post',
  pillar       text,
  caption      text not null default '',
  caption_alt  text,
  image_prompt text,
  sources      jsonb not null default '[]',
  risk         text,
  qa_notes     text,
  folder       text not null check (folder in ('pending','sent','approved','rejected','posted')),
  chosen       text,
  final_caption text,
  edited       boolean not null default false,
  post_url     text,
  reject_note  text,
  extra        jsonb not null default '{}',
  updated_at   timestamptz not null default now(),
  updated_by   text not null default 'local'
);
drop trigger if exists drafts_audit on public.drafts;
create trigger drafts_audit before insert or update on public.drafts for each row execute function public.set_audit();
alter table public.drafts enable row level security;
drop policy if exists "staff read drafts" on public.drafts;
create policy "staff read drafts" on public.drafts for select to authenticated using (public.is_staff());
drop policy if exists "staff update drafts" on public.drafts;
create policy "staff update drafts" on public.drafts for update to authenticated using (public.is_staff()) with check (public.is_staff());

-- 4) Kế hoạch, chủ đề, trạng thái nguồn, báo cáo nội bộ (chỉ máy chủ chính ghi, nhân viên chỉ đọc)
create table if not exists public.plans (
  week text primary key, range text, notes text,
  slots jsonb not null default '[]', trial_today jsonb not null default '[]', raw jsonb,
  src_mtime timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.topics (
  file text primary key, items jsonb not null default '[]',
  src_mtime timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.source_runs (
  week text primary key, "window" text, collected_at timestamptz, items jsonb not null default '[]',
  updated_at timestamptz not null default now()
);
create table if not exists public.reports_internal (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('weekly','monthly')),
  period text not null, title text not null, body_md text not null,
  updated_at timestamptz not null default now(),
  unique (kind, period)
);
alter table public.plans enable row level security;
alter table public.topics enable row level security;
alter table public.source_runs enable row level security;
alter table public.reports_internal enable row level security;
drop policy if exists "staff read plans" on public.plans;
create policy "staff read plans" on public.plans for select to authenticated using (public.is_staff());
drop policy if exists "staff read topics" on public.topics;
create policy "staff read topics" on public.topics for select to authenticated using (public.is_staff());
drop policy if exists "staff read source_runs" on public.source_runs;
create policy "staff read source_runs" on public.source_runs for select to authenticated using (public.is_staff());
drop policy if exists "staff read reports_internal" on public.reports_internal;
create policy "staff read reports_internal" on public.reports_internal for select to authenticated using (public.is_staff());

-- 5) Phản hồi khi bỏ/sửa bài (nhân viên thêm, máy chủ chính nhận về để agent học)
create table if not exists public.feedback (
  id         bigint generated always as identity primary key,
  draft_id   text,
  feedback   text not null,
  source     text not null default 'web',
  synced     boolean not null default false,
  created_at timestamptz not null default now(),
  created_by text not null default coalesce(nullif(auth.jwt() ->> 'email', ''), 'local')
);
alter table public.feedback enable row level security;
drop policy if exists "staff read feedback" on public.feedback;
create policy "staff read feedback" on public.feedback for select to authenticated using (public.is_staff());
drop policy if exists "staff add feedback" on public.feedback;
create policy "staff add feedback" on public.feedback for insert to authenticated with check (public.is_staff() and source = 'web' and synced = false);

-- 6) Cấp quyền thủ công (đã tắt tự mở bảng). Nhân viên chỉ có quyền tối thiểu.
revoke all on public.staff, public.drafts, public.plans, public.topics, public.source_runs, public.reports_internal, public.feedback from anon, authenticated;
grant select on public.drafts, public.plans, public.topics, public.source_runs, public.reports_internal, public.feedback to authenticated;
grant update (caption, caption_alt, folder, chosen, final_caption, edited, post_url, reject_note) on public.drafts to authenticated;
grant insert (draft_id, feedback) on public.feedback to authenticated;
grant all on public.staff, public.drafts, public.plans, public.topics, public.source_runs, public.reports_internal, public.feedback to service_role;
grant usage, select on all sequences in schema public to service_role;
