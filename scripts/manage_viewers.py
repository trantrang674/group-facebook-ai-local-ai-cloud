"""Quản lý người được xem báo cáo.
  python scripts/manage_viewers.py list
  python scripts/manage_viewers.py add email@example.com "ghi chú"   # thêm vào danh sách + gửi email mời
  python scripts/manage_viewers.py remove email@example.com          # thu hồi quyền đọc (xóa khỏi danh sách)
Thu hồi chỉ cần xóa khỏi danh sách: RLS sẽ chặn đọc ngay, dù tài khoản đăng nhập của họ vẫn còn.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "list":
        rows = supa.rest("GET", "viewers?select=email,note,created_at&order=created_at").json()
        for r in rows:
            print(f"{r['email']:40} {r.get('note') or ''}")
        print(f"({len(rows)} người)")
    elif cmd == "add" and len(a) >= 2:
        email = a[1].strip().lower()
        if not EMAIL.match(email):
            sys.exit("Email không hợp lệ")
        supa.rest("POST", "viewers?on_conflict=email", json={"email": email, "note": a[2] if len(a) > 2 else None},
                  hdr={"Prefer": "resolution=merge-duplicates,return=minimal"})
        print("Đã thêm vào danh sách xem:", email)
        try:
            supa.auth_admin("POST", "invite", json={"email": email})
            print("Đã gửi email mời đăng nhập.")
        except RuntimeError as e:
            print("Chưa gửi được email mời (có thể tài khoản đã tồn tại hoặc bị giới hạn gửi email):", e)
    elif cmd == "remove" and len(a) >= 2:
        email = a[1].strip().lower()
        if not EMAIL.match(email):
            sys.exit("Email không hợp lệ")
        supa.rest("DELETE", "viewers", params={"email": "eq." + email})
        print("Đã thu hồi quyền xem của", email)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
