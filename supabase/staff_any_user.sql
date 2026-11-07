-- MỌI TÀI KHOẢN ĐĂNG NHẬP HỢP LỆ = NHÂN VIÊN (không cần thêm email vào bảng staff nữa).
-- Chạy MỘT LẦN trong Supabase: SQL Editor -> New query -> dán -> Run.
--
-- AN TOÀN PHỤ THUỘC VÀO: Authentication -> Providers -> Email -> "Allow new users to sign up" phải TẮT (hiện đang tắt),
-- không bật đăng nhập ẩn danh, không bật nhà cung cấp đăng nhập khác (Google...). Nếu ai đó bật lại đăng ký tự do,
-- BẤT KỲ AI cũng tự tạo tài khoản và đọc được toàn bộ dữ liệu. Muốn thêm nhân viên: tạo tài khoản trong Authentication -> Users.
--
-- Hàm kiểm tra trực tiếp bảng auth.users nên khi bạn XÓA hoặc CHẶN (Ban) một tài khoản, quyền bị thu hồi NGAY,
-- không phải chờ phiên đăng nhập cũ hết hạn.
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