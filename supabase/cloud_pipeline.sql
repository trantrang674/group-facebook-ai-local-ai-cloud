-- CHO QUY TRÌNH TỰ ĐỘNG TRÊN GITHUB ACTIONS. Chạy MỘT LẦN trong Supabase: SQL Editor -> New query -> dán -> Run.
-- Bảng private_files giữ các file riêng tư (Brand Brain, FAQ, danh sách kênh, bộ đếm lượt API) để runner trên đám mây tải về
-- khi chạy (repo công khai nên KHÔNG chứa các file này). Không có policy nào cho người dùng đăng nhập: nhân viên và khách
-- đều KHÔNG đọc được; chỉ khóa service_role (nằm trong GitHub Secrets và .env trên máy bạn) mới truy cập.
create table if not exists public.private_files (
  path       text primary key,
  content    text not null,
  updated_at timestamptz not null default now()
);
alter table public.private_files enable row level security;
revoke all on public.private_files from anon, authenticated;
grant all on public.private_files to service_role;
