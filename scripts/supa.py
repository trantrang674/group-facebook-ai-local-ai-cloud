"""Hàm gọi Supabase bằng service_role key (CHỈ chạy trên máy bạn, khóa nằm trong .env, không bao giờ đưa lên trang web)."""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
TIMEOUT = 30


def cfg():
    url = (os.getenv("SUPABASE_PROJECT_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise SystemExit("Thiếu SUPABASE_PROJECT_URL hoặc SUPABASE_SERVICE_ROLE_KEY trong .env")
    if not url.startswith("https://"):
        raise SystemExit("SUPABASE_PROJECT_URL phải bắt đầu bằng https:// (ví dụ https://abcd1234.supabase.co)")
    return url, key


def _headers(extra=None):
    _, key = cfg()
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def rest(method, path, hdr=None, **kw):
    """Gọi PostgREST: rest('GET', 'reports?select=id'). `hdr` là header thêm (ví dụ Prefer)."""
    url, _ = cfg()
    r = requests.request(method, f"{url}/rest/v1/{path}", headers=_headers(hdr), timeout=TIMEOUT, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"Supabase REST {r.status_code}: {r.text[:300]}")
    return r


def auth_admin(method, path, **kw):
    url, _ = cfg()
    r = requests.request(method, f"{url}/auth/v1/{path}", headers=_headers(), timeout=TIMEOUT, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"Supabase Auth {r.status_code}: {r.text[:300]}")
    return r
