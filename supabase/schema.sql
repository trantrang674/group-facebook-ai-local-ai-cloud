-- Chạy MỘT LẦN trong Supabase: SQL Editor -> New query -> dán toàn bộ -> Run.
-- Thiết lập: "Automatically expose new tables" TẮT và "automatic RLS" BẬT, nên mọi quyền đều cấp thủ công ở dưới.

-- 1) Danh sách email được phép xem báo cáo
create table if not exists public.viewers (
  email      text primary key,
  note       text,
  created_at timestamptz not null default now()
);
alter table public.viewers enable row level security;   -- không tạo policy nào: người dùng thường không đọc được bảng này

-- 2) Báo cáo đã lược bỏ phần nội bộ
create table if not exists public.reports (
  id           bigint generated always as identity primary key,
  kind         text not null check (kind in ('weekly','monthly')),
  period       text not null,                      -- ví dụ 2026-11-02 (thứ Hai của tuần) hoặc 2026-10 (tháng)
  title        text not null,
  body_md      text not null,
  published_at timestamptz not null default now(),
  unique (kind, period)
);
alter table public.reports enable row level security;

-- 3) Hàm kiểm tra "người đang đăng nhập có nằm trong danh sách mời không"
--    security definer để đọc được bảng viewers dù người dùng không có quyền trực tiếp.
create or replace function public.is_viewer()
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select exists (
    select 1 from public.viewers v
    where lower(v.email) = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;
revoke all on function public.is_viewer() from public, anon;
grant execute on function public.is_viewer() to authenticated;

-- 4) Quy tắc đọc: chỉ người đã đăng nhập VÀ nằm trong danh sách mời
drop policy if exists "viewers can read reports" on public.reports;
create policy "viewers can read reports"
  on public.reports for select
  to authenticated
  using (public.is_viewer());

-- 5) Cấp quyền thủ công (vì đã tắt tự mở bảng)
revoke all on public.reports, public.viewers from anon, authenticated;
grant select on public.reports to authenticated;                 -- đọc, nhưng vẫn bị RLS lọc
grant all on public.reports, public.viewers to service_role;     -- script trên máy bạn (bỏ qua RLS)
grant usage, select on all sequences in schema public to service_role;
