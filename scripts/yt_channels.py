"""Quét video (dài + Shorts) của các kênh trong config/youtube_channels.txt trong cửa sổ tuần (thứ Hai -> Chủ nhật,
giờ Việt Nam), rồi lấy transcript cho TOP N video đáng làm nội dung nhất.

Cách lấy danh sách video (tự chọn):
  1) YouTube Data API chính thức nếu có YOUTUBE_API_KEY (miễn phí; quét 6 kênh tốn khoảng 10-20 đơn vị/tuần).
     Shorts nhận diện theo thời lượng <= 180 giây.
  2) RSS công khai của YouTube nếu không có khóa (có thể bị 404 ở một số mạng).
Chọn video lấy transcript (mặc định 10/tuần, đặt YT_TRANSCRIPTS_PER_WEEK để đổi):
  - Chấm độ phù hợp bằng số từ khóa trong config/relevance_keywords.txt (tiêu đề + mô tả).
  - Ưu tiên video phù hợp (>= 1 từ khóa), xếp theo lượt xem giảm dần. Mỗi transcript tốn 1 search SerpAPI.
  - Nếu có ít hơn N video phù hợp thì KHÔNG lấp bằng video lạc đề (đặt YT_FILL_WITH_TOP_VIEWS=1 để lấp bằng video nhiều view nhất).
"""
import datetime as dt
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")  # để chạy riêng được
except ImportError:
    pass
CONF = ROOT / "config" / "youtube_channels.txt"
KEYWORDS = ROOT / "config" / "relevance_keywords.txt"
CACHE = ROOT / "data" / "youtube_channels_cache.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) tnc-group-agent/0.1", "Accept-Language": "vi,en;q=0.8"}
COOKIES = {"CONSENT": "YES+1", "SOCS": "CAI"}
TIMEOUT = 20
VN = dt.timezone(dt.timedelta(hours=7))


def _read(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def channel_urls():
    out = []
    for line in CONF.read_text(encoding="utf-8").splitlines() if CONF.exists() else []:
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def keywords():
    return [_norm(k.strip()) for k in (KEYWORDS.read_text(encoding="utf-8").splitlines() if KEYWORDS.exists() else [])
            if k.strip() and not k.startswith("#")]


def relevance(title, desc, kws):
    """Đếm từ khóa khớp. Từ ngắn (<=3 ký tự, ví dụ 'ai', 'api', 'rag') chỉ tính khi viết HOA trong nguyên văn,
    vì 'ai' viết thường là từ tiếng Việt thông thường ('chả ai xài') và sẽ gây khớp nhầm."""
    raw = f"{title} {desc}"
    low = _norm(raw)
    up = unicodedata.normalize("NFD", raw.replace("Đ", "D"))
    up = "".join(c for c in up if unicodedata.category(c) != "Mn")
    n = 0
    for k in kws:
        if len(k) <= 3 and k.isalpha():
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(k.upper()) + r"(?![A-Za-z0-9])", up):
                n += 1
        elif re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", low):
            n += 1
    return n


def resolve(url, cache):
    """Trả (channel_id, tên). Dùng cache; nếu chưa có thì đọc trang kênh một lần."""
    m = re.search(r"youtube\.com/channel/(UC[\w-]{20,24})", url)
    if m:
        return m.group(1), cache.get(url, {}).get("name") or m.group(1)
    if url in cache:
        return cache[url]["id"], cache[url].get("name")
    hm = re.search(r"youtube\.com/(@[\w.\-]+)", url)
    if not hm:
        raise ValueError("link không đúng dạng @handle hoặc /channel/UC...")
    r = requests.get(f"https://www.youtube.com/{hm.group(1)}", headers=UA, cookies=COOKIES, timeout=TIMEOUT)
    r.raise_for_status()
    for pat in (r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{20,24})"',
                r'"externalId":"(UC[\w-]{20,24})"', r'feeds/videos\.xml\?channel_id=(UC[\w-]{20,24})',
                r'"channelId":"(UC[\w-]{20,24})"'):
        mm = re.search(pat, r.text)
        if mm:
            t = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
            name = t.group(1) if t else hm.group(1)
            cache[url] = {"id": mm.group(1), "name": name}
            return mm.group(1), name
    raise ValueError("không tìm thấy ID kênh (YouTube có thể chặn). Dùng link dạng /channel/UC...")


def _iso_seconds(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def _api_videos(cid, key, t0, t1):
    base = "https://www.googleapis.com/youtube/v3"
    r = requests.get(f"{base}/playlistItems", params={"part": "snippet,contentDetails", "playlistId": "UU" + cid[2:],
                                                      "maxResults": 50, "key": key}, timeout=TIMEOUT)
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:120])
        except ValueError:
            msg = r.text[:120]
        raise RuntimeError(f"YouTube API {r.status_code}: {msg}")
    items = []
    for it in r.json().get("items", []):
        pub = it["contentDetails"].get("videoPublishedAt") or it["snippet"].get("publishedAt")
        try:
            pubdt = dt.datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            continue
        if not (t0 <= pubdt < t1):
            continue
        items.append({"video_id": it["contentDetails"]["videoId"], "title": it["snippet"].get("title"),
                      "published": pubdt, "description": (it["snippet"].get("description") or "")[:400]})
    if items:
        r = requests.get(f"{base}/videos", params={"part": "contentDetails,statistics", "id": ",".join(i["video_id"] for i in items),
                                                   "key": key}, timeout=TIMEOUT)
        r.raise_for_status()
        info = {v["id"]: v for v in r.json().get("items", [])}
        for i in items:
            v = info.get(i["video_id"], {})
            secs = _iso_seconds((v.get("contentDetails") or {}).get("duration"))
            i["kind"] = "short" if secs is not None and secs <= 180 else "video"
            i["seconds"] = secs
            try:
                i["views"] = int((v.get("statistics") or {}).get("viewCount"))
            except (TypeError, ValueError):
                i["views"] = None
    return items


def _rss_videos(cid, t0, t1):
    out = []
    for kind, prefix in (("video", "UULF"), ("short", "UUSH")):
        d = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?playlist_id={prefix}{cid[2:]}",
                             request_headers={"User-Agent": UA["User-Agent"]})
        if d.get("bozo") and not d.entries:
            raise RuntimeError(f"RSS lỗi (HTTP {d.get('status')}) - cân nhắc đặt YOUTUBE_API_KEY")
        for e in d.entries:
            try:
                pub = dt.datetime.fromtimestamp(time.mktime(e.published_parsed), dt.timezone.utc)
            except (AttributeError, OverflowError, ValueError, TypeError):
                continue
            if not (t0 <= pub < t1):
                continue
            try:
                views = int((e.get("media_statistics") or {}).get("views"))
            except (TypeError, ValueError):
                views = None
            out.append({"video_id": e.get("yt_videoid"), "title": e.get("title"), "published": pub, "kind": kind,
                        "views": views, "seconds": None, "description": (e.get("summary") or "")[:400]})
    return out


def scan(win):
    urls = channel_urls()
    if not urls:
        return {"skipped": "chưa có kênh trong config/youtube_channels.txt"}
    t0 = dt.datetime.combine(win["start"], dt.time.min, VN)
    t1 = dt.datetime.combine(win["end"] + dt.timedelta(days=1), dt.time.min, VN)
    cache, kws = _read(CACHE, {}), keywords()
    key = os.getenv("YOUTUBE_API_KEY")
    videos, errors = [], []
    for url in urls:
        try:
            cid, name = resolve(url, cache)
            items = _api_videos(cid, key, t0, t1) if key else _rss_videos(cid, t0, t1)
        except Exception as e:  # noqa: BLE001
            errors.append({"channel": url, "error": str(e)[:200]})
            continue
        for i in items:
            if not i.get("video_id"):
                continue
            rel = relevance(i["title"], i["description"], kws)
            videos.append({"channel": name, "channel_url": url, "kind": i["kind"], "video_id": i["video_id"],
                           "title": i["title"], "published": i["published"].astimezone(VN).isoformat(),
                           "link": f"https://www.youtube.com/{'shorts/' if i['kind'] == 'short' else 'watch?v='}{i['video_id']}",
                           "views": i.get("views"), "seconds": i.get("seconds"), "relevance": rel,
                           "description": i["description"][:300]})
    _write(CACHE, cache)
    if not videos and errors:
        raise RuntimeError("; ".join(f"{x['channel']}: {x['error']}" for x in errors[:3]))
    videos.sort(key=lambda v: v["views"] or 0, reverse=True)

    # Chọn top N để lấy transcript: ưu tiên video phù hợp, rồi xếp theo lượt xem.
    n = int(os.getenv("YT_TRANSCRIPTS_PER_WEEK", "10"))
    picks = [v for v in videos if v["relevance"] >= 1][:n]
    if len(picks) < n and os.getenv("YT_FILL_WITH_TOP_VIEWS") == "1":
        picks += [v for v in videos if v not in picks][: n - len(picks)]
    for rank, v in enumerate(picks, 1):
        v["transcript_rank"] = rank

    fetched, no_key = [], True
    try:
        import serp
        no_key = not serp.key()
        if not no_key:
            for v in picks:
                try:
                    r = serp.transcript(v["video_id"], "vi")
                    fetched.append({"rank": v["transcript_rank"], "video_id": v["video_id"], "channel": v["channel"],
                                    "title": v["title"], "views": v["views"], "relevance": v["relevance"],
                                    "segments": r["segments"], "error": r["error"]})
                except serp.OutOfBudget:
                    break
                except Exception as e:  # noqa: BLE001
                    fetched.append({"rank": v["transcript_rank"], "video_id": v["video_id"], "error": str(e)[:160]})
    except ImportError:
        pass
    return {"window": f"{win['start']}..{win['end']}", "channels": len(urls), "total": len(videos),
            "transcript_candidates": len(picks), "videos": videos, "transcripts_fetched": fetched,
            "transcript_skipped_reason": "thiếu SERPAPI_KEY nên chưa lấy transcript" if no_key else None,
            "errors": errors}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from collect_sources import week_window
    r = scan(week_window())
    print(json.dumps({k: v for k, v in r.items() if k != "videos"}, ensure_ascii=False, indent=2))
    for v in r.get("videos", [])[:15]:
        print(f"{v['kind']:5} {v['published'][:10]} {v['views']!s:>8} rel={v['relevance']:<2} {v['channel'][:16]:16} {v['title'][:55]}")
