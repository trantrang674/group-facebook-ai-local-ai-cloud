"""Thu thập dữ liệu thô MỖI TUẦN (chạy sáng thứ Hai) cho cửa sổ thứ Hai -> Chủ nhật của tuần trước (7 ngày, giờ VN).

Kết quả: data/weekly/<ngày thứ Hai của cửa sổ>/*.json   (ví dụ chạy 09/11/2026 -> data/weekly/2026-11-02/)
Dùng:
  python scripts/collect_sources.py                     # cửa sổ = tuần Thứ Hai..Chủ nhật vừa kết thúc
  python scripts/collect_sources.py --week 2026-11-02   # chạy bù cho tuần bắt đầu thứ Hai này (Serper lọc lệch, xem serp.py)
  python scripts/collect_sources.py --week 2026-11-02 --end 2026-11-06   # rút ngắn cửa sổ (ví dụ thứ Hai..thứ Sáu)
Mỗi nguồn độc lập: một nguồn lỗi không làm hỏng các nguồn khác.
"""
import datetime as dt
import json
import socket
import sys
import time
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))
UA = {"User-Agent": "tnc-group-agent/0.1"}
TIMEOUT = 20
socket.setdefaulttimeout(TIMEOUT)  # feedparser không có timeout riêng
VN = dt.timezone(dt.timedelta(hours=7))

RSS_FEEDS = {
    "hf_blog": "https://huggingface.co/blog/feed.xml",
    "ollama_releases": "https://github.com/ollama/ollama/releases.atom",
    "llamacpp_releases": "https://github.com/ggml-org/llama.cpp/releases.atom",
    "lmstudio_blog": "https://lmstudio.ai/blog/rss.xml",
    "the_verge_ai": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "tomshardware": "https://www.tomshardware.com/feeds/all",
}
DOWN = ["Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy", "Chủ nhật"]


def week_window(today=None, monday=None, end=None):
    """Cửa sổ thứ Hai..Chủ nhật. Mặc định: tuần trọn vẹn gần nhất đã kết thúc (chạy sáng thứ Hai -> tuần trước).
    `end` (tùy chọn) rút ngắn cửa sổ, ví dụ thứ Sáu khi cần chạy sớm."""
    if monday:
        start = monday
    else:
        today = today or dt.datetime.now(VN).date()
        start = today - dt.timedelta(days=today.weekday() + 7)  # thứ Hai của tuần trước
    last = start + dt.timedelta(days=6)
    if end:
        if not (start <= end <= last):
            raise SystemExit("--end phải nằm trong cùng tuần với --week (từ thứ Hai đến Chủ nhật)")
        last = end
    return {"start": start, "end": last, "label": start.isoformat()}


WIN = None
OUT = None


def _in_window(ts_struct):
    """ts_struct: struct_time UTC. True nếu ngày (giờ VN) nằm trong cửa sổ; không có ngày thì giữ lại."""
    if not ts_struct:
        return True
    d = dt.datetime.fromtimestamp(time.mktime(ts_struct), dt.timezone.utc).astimezone(VN).date()
    return WIN["start"] <= d <= WIN["end"]


def save(name, data):
    (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = isinstance(data, dict) and ("error" in data or "skipped" in data)
    print(f"[{'bo qua/loi' if failed else 'ok'}] {name}")


def safe(name, fn):
    def run():
        try:
            save(name, fn(WIN) if fn.__code__.co_argcount else fn())
        except Exception as e:  # noqa: BLE001
            print(f"[loi] {name}: {e}", file=sys.stderr)
            save(name, {"error": str(e)})
    return run


def rss():
    items = []
    for src, url in RSS_FEEDS.items():
        for e in feedparser.parse(url).entries[:40]:
            if not _in_window(e.get("published_parsed") or e.get("updated_parsed")):
                continue
            items.append({"source": src, "title": e.get("title"), "link": e.get("link"),
                          "published": e.get("published", e.get("updated", "")), "summary": (e.get("summary") or "")[:500]})
    return items


def huggingface():
    # Danh sách "trending" tại thời điểm chạy (không có bộ lọc theo ngày).
    r = requests.get("https://huggingface.co/api/models?sort=trendingScore&limit=30", headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [{"id": m["id"], "likes": m.get("likes"), "downloads": m.get("downloads"),
             "pipeline": m.get("pipeline_tag"), "link": f"https://huggingface.co/{m['id']}"} for m in r.json()]


def main():
    global WIN, OUT
    args = sys.argv[1:]
    monday = None
    if "--week" in args:
        monday = dt.date.fromisoformat(args[args.index("--week") + 1])
        if monday.weekday() != 0:
            sys.exit("--week phải là một ngày thứ Hai (YYYY-MM-DD)")
    end = dt.date.fromisoformat(args[args.index("--end") + 1]) if "--end" in args else None
    WIN = week_window(monday=monday, end=end)
    OUT = ROOT / "data" / "weekly" / WIN["label"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_window.json").write_text(json.dumps(
        {"start": WIN["start"].isoformat(), "end": WIN["end"].isoformat(),
         "collected_at": dt.datetime.now(VN).isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Cửa sổ thu thập: {WIN['start']} (thứ {DOWN[WIN['start'].weekday()]}) .. {WIN['end']} (thứ {DOWN[WIN['end'].weekday()]})")
    import serp
    import yt_channels
    steps = [
        ("rss", rss), ("serper_news", serp.news), ("serper_search", serp.search), ("serper_autocomplete", serp.autocomplete),
        ("serpapi_trends", serp.trends), ("youtube_channels", yt_channels.scan), ("huggingface", huggingface),
    ]
    for name, fn in steps:
        safe(name, fn)()
    print("Đã lưu vào", OUT)


if __name__ == "__main__":
    main()
