"""Quản lý nhân viên. MÔ HÌNH: mọi tài khoản trong Supabase Authentication -> Users = nhân viên (xem, sửa, duyệt bài).
Vì vậy muốn thêm nhân viên: tạo tài khoản ở Supabase (Add user -> Create new user, tick Auto Confirm User). Giữ "Allow new users to sign up" TẮT.
  python scripts/manage_staff.py list                  # liệt kê tài khoản = nhân viên
  python scripts/manage_staff.py remove email --yes    # XÓA tài khoản (thu hồi ngay lập tức, không khôi phục được)
Nhân viên đọc được TOÀN BỘ bài nháp, kế hoạch, chủ đề, báo cáo và sửa/duyệt được bài.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def users():
    return supa.auth_admin("GET", "admin/users", params={"per_page": 200}).json().get("users", [])


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "list":
        us = users()
        for u in us:
            print(f"{(u.get('email') or ''):40} đăng nhập cuối: {(u.get('last_sign_in_at') or 'chưa')[:19]}")
        print(f"({len(us)} nhân viên)")
    elif a[0] == "remove" and len(a) >= 2:
        email = a[1].strip().lower()
        if not EMAIL.match(email):
            sys.exit("Email không hợp lệ")
        if "--yes" not in a:
            sys.exit(f"Sẽ XÓA tài khoản {email} (không khôi phục được). Chạy lại kèm --yes để xác nhận.")
        match = [u for u in users() if (u.get("email") or "").lower() == email]
        if not match:
            sys.exit("Không thấy tài khoản này")
        supa.auth_admin("DELETE", f"admin/users/{match[0]['id']}")
        print("Đã xóa tài khoản và thu hồi quyền của", email)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
