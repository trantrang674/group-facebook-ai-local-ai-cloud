"""Kiểm tra từng kết nối API. Không in giá trị khóa.
Dùng: python scripts/check_env.py            (kiểm tra tất cả)
      python scripts/check_env.py serper serpapi (chỉ vài mục: telegram serper serpapi)
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
T = 20


def need(*keys):
    miss = [k for k in keys if not os.getenv(k)]
    return miss


def telegram():
    if need("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        return "thiếu " + ", ".join(need("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))
    r = requests.get(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/getMe", timeout=T)
    r.raise_for_status()
    return "OK, bot @" + r.json()["result"]["username"]


def serpapi():
    if need("SERPAPI_KEY"):
        return "thiếu SERPAPI_KEY"
    r = requests.get("https://serpapi.com/account.json", params={"api_key": os.environ["SERPAPI_KEY"]}, timeout=T)
    if r.status_code != 200:
        return f"LỖI {r.status_code}: khóa sai hoặc bị từ chối"
    j = r.json()
    left = j.get("total_searches_left", j.get("plan_searches_left", "?"))
    return f"OK, gói {j.get('plan_name', '?')}, còn {left} search tháng này"


def serper():
    if need("SERPER_API_KEY"):
        return "thiếu SERPER_API_KEY"
    # Thử 1 truy vấn nhỏ (tốn 1 credit) vì Serper không có endpoint kiểm tra tài khoản đã xác nhận.
    r = requests.post("https://google.serper.dev/search", json={"q": "ollama", "num": 1},
                      headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"}, timeout=T)
    if r.status_code in (401, 403):
        return f"LỖI {r.status_code}: khóa sai hoặc hết credit"
    if r.status_code != 200:
        return f"LỖI {r.status_code}: {r.text[:150]}"
    return "OK, khóa hoạt động (đã dùng 1 credit để thử)"


def youtube():
    if need("YOUTUBE_API_KEY"):
        return "thiếu YOUTUBE_API_KEY (tùy chọn)"
    r = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
        "part": "snippet", "forHandle": "@Google", "key": os.environ["YOUTUBE_API_KEY"]}, timeout=T)
    if r.status_code != 200:
        return f"LỖI {r.status_code}: " + r.json().get("error", {}).get("message", "")[:200]
    return "OK, khóa YouTube hoạt động"


def supabase():
    if need("SUPABASE_PROJECT_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        return "thiếu " + ", ".join(need("SUPABASE_PROJECT_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    url = os.environ["SUPABASE_PROJECT_URL"].strip().rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
    if not url.startswith("https://"):
        return "SUPABASE_PROJECT_URL phải bắt đầu bằng https://"
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = requests.get(f"{url}/auth/v1/admin/users", params={"per_page": 1}, headers=h, timeout=T)
    if r.status_code in (401, 403):
        return f"LỖI {r.status_code}: khóa service_role sai (hoặc nhầm sang anon key)"
    if r.status_code != 200:
        return f"LỖI {r.status_code}: {r.text[:150]}"
    t = requests.get(f"{url}/rest/v1/reports", params={"select": "id", "limit": 1}, headers=h, timeout=T)
    schema = "đã có bảng reports" if t.status_code == 200 else "CHƯA chạy supabase/schema.sql (chưa có bảng reports)"
    d = requests.get(f"{url}/rest/v1/drafts", params={"select": "id", "limit": 1}, headers=h, timeout=T)
    staff = "đã có bảng cho nhân viên" if d.status_code == 200 else "CHƯA chạy supabase/schema_staff.sql (bản web nhân viên chưa dùng được)"
    return f"OK, khóa service_role hoạt động; {schema}; {staff}"


CHECKS = {"telegram": telegram, "serper": serper, "serpapi": serpapi, "youtube": youtube, "supabase": supabase}

if __name__ == "__main__":
    pick = sys.argv[1:] or list(CHECKS)
    for name in pick:
        try:
            print(f"[{name}] {CHECKS[name]()}")
        except KeyError:
            print(f"[{name}] không có mục này. Chọn: {', '.join(CHECKS)}")
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] LỖI: {str(e)[:250]}")
