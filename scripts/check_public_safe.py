"""Chốt chặn trước khi commit (repo này CÔNG KHAI). Chạy tự động bởi .git/hooks/pre-commit; chạy tay: python scripts/check_public_safe.py
Chặn commit nếu có: file dữ liệu riêng tư, mẫu khóa bí mật, hoặc email thật dùng làm tác giả commit.
"""
import re
import subprocess
import sys

FORBIDDEN_PATH = re.compile(
    r"^(data/|reports/|logs/|secrets/|\.env$|\.env\.(?!example$)|brand/(?!.*\.example\.md$)|config/youtube_channels\.txt$)"
    r"|(^|/)(service-account|credentials)[^/]*\.json$|\.json\.key$", re.I)
SECRET = re.compile(
    r"sb_secret_[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{30,}|\b[0-9]{8,10}:AA[0-9A-Za-z_-]{30,}"
    r"|eyJ[A-Za-z0-9_-]{40,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"
    r"|(SERVICE_ROLE_KEY|BOT_TOKEN|API_KEY|SERPAPI_KEY|SERPER_API_KEY)[ \t]*=[ \t]*['\"]?[A-Za-z0-9_\-]{16,}")
PERSONAL = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+|\b[\w.+-]+@(gmail|yahoo|outlook|hotmail)\.[a-z.]+\b", re.I)


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def main():
    problems = []
    files = [f for f in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if f]
    for f in files:
        if FORBIDDEN_PATH.search(f):
            problems.append(f"file riêng tư không được công khai: {f}")
            continue
        content = git("show", f":{f}")
        if SECRET.search(content):
            problems.append(f"có mẫu khóa bí mật trong: {f}")
        m = PERSONAL.search(content)
        if m and f != "scripts/check_public_safe.py":
            problems.append(f"có thông tin cá nhân ({m.group(0)[:30]}…) trong: {f}")
    email = git("config", "user.email").strip()
    if not email.endswith("@users.noreply.github.com"):
        problems.append("user.email không phải địa chỉ noreply của GitHub: email thật sẽ lộ công khai trong lịch sử commit. "
                        "Chạy: git config user.email <tên-tài-khoản>@users.noreply.github.com")
    if problems:
        print("\n=== COMMIT BỊ CHẶN (repo công khai) ===")
        for p in problems:
            print(" -", p)
        print("Sửa xong rồi commit lại. Không nên dùng --no-verify để bỏ qua.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
