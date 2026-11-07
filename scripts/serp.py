"""Nguồn tìm kiếm cho collect_sources.py (chạy MỖI TUẦN, sáng thứ Hai, quét 7 ngày thứ Hai -> Chủ nhật tuần trước).

SERPER (google.serper.dev): news(win), search(win) (kèm People Also Ask + Related Searches), autocomplete(win)
SERPAPI (serpapi.com): trends(win) và transcript() (lấy theo từng video do yt_channels gọi)

`win` = {"start": date, "end": date, "label": "YYYY-MM-DD"} (xem collect_sources.week_window).
Lưu ý độ chính xác: Serper lọc thời gian theo "7 ngày gần nhất tính từ lúc chạy" (qdr:w), nên chỉ đúng khi chạy vào
sáng thứ Hai. Nếu chạy bù tuần cũ thì kết quả tin tức/tìm kiếm lệch cửa sổ (file kết quả có ghi chú).

Mỗi nhà cung cấp có bộ đếm riêng trong data/.serpapi_usage.json và tự DỪNG khi chạm ngân sách.
Biến .env tùy chọn:
  SERPER_API_KEY, SERPER_TOTAL_CREDITS (mặc định 2500, gói miễn phí dùng một lần, không reset theo tháng)
  SERPAPI_KEY, SERPAPI_MONTHLY_BUDGET (mặc định 250)
"""
import datetime as dt
import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
USAGE = ROOT / "data" / ".serpapi_usage.json"
TIMEOUT = 30


class OutOfBudget(Exception):
    pass


# ---------- bộ đếm dùng chung ----------
def _load():
    month = dt.date.today().strftime("%Y-%m")
    try:
        u = json.loads(USAGE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        u = {}
    if u.get("month") != month:  # SerpAPI reset theo tháng; Serper (serper_used) cộng dồn
        u = {"month": month, "used": 0, "last": u.get("last", {}), "serper_used": u.get("serper_used", 0)}
    u.setdefault("last", {})
    u.setdefault("serper_used", 0)
    return u


def _save(u):
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(u, ensure_ascii=False, indent=2), encoding="utf-8")


def usage():
    u = _load()
    return {"month": u["month"], "used": u["used"], "budget": int(os.getenv("SERPAPI_MONTHLY_BUDGET", "250")),
            "serper_used": u["serper_used"], "serper_total": int(os.getenv("SERPER_TOTAL_CREDITS", "2500"))}


# ---------- Serper ----------
def serper_key():
    return os.getenv("SERPER_API_KEY")


def serper(endpoint, body):
    """POST https://google.serper.dev/<endpoint>, header X-API-KEY. Có chặn ngân sách; đếm credit theo phản hồi."""
    u = _load()
    total = int(os.getenv("SERPER_TOTAL_CREDITS", "2500"))
    if u["serper_used"] >= total:
        raise OutOfBudget(f"Serper: đã dùng {u['serper_used']}/{total} credit, dừng")
    r = requests.post(f"https://google.serper.dev/{endpoint}", json=body, timeout=TIMEOUT,
                      headers={"X-API-KEY": serper_key(), "Content-Type": "application/json"})
    if r.status_code in (401, 403):
        raise RuntimeError(f"Serper {r.status_code}: khóa SERPER_API_KEY sai hoặc hết credit")
    if r.status_code != 200:
        raise RuntimeError(f"Serper {r.status_code}: {r.text[:160]}")
    try:
        j = r.json()
    except ValueError:
        raise RuntimeError("Serper trả về không phải JSON: " + r.text[:120])
    credits = j.get("credits", 1)
    u["serper_used"] += credits if isinstance(credits, int) and credits > 0 else 1
    _save(u)
    return j


def _skip_serper():
    return {"skipped": "thiếu SERPER_API_KEY"} if not serper_key() else None


def _offset_note(win):
    """Cảnh báo nếu không phải chạy vào tuần ngay sau cửa sổ (Serper lọc theo 7 ngày gần nhất tính từ hôm nay)."""
    gap = (dt.date.today() - win["end"]).days
    return None if 0 <= gap <= 2 else f"Chạy cách cuối cửa sổ {gap} ngày: tin tức/tìm kiếm của Serper lệch cửa sổ {win['start']}..{win['end']}"


NEWS_QUERIES = [  # (truy vấn, gl, hl)
    ("Ollama OR \"local LLM\" OR \"open-weight model\"", "us", "en"),
    ("\"chạy AI trên máy tính\" OR \"AI local\" OR \"mô hình AI mã nguồn mở\" OR Ollama", "vn", "vi"),
    ("\"run LLM locally\" OR llama.cpp OR \"LM Studio\"", "us", "en"),
    ("\"new open-source AI model\" OR \"open weights\"", "us", "en"),
    ("mô hình AI mã nguồn mở mới", "vn", "vi"),
    ("\"vibe coding\" OR \"AI coding agent\" OR \"Claude Code\"", "us", "en"),
]


def news(win):
    if _skip_serper():
        return _skip_serper()
    seen, out = set(), []
    for q, gl, hl in NEWS_QUERIES:
        j = serper("news", {"q": q, "gl": gl, "hl": hl, "num": 10, "tbs": "qdr:w"})
        for n in (j.get("news") or [])[:15]:
            link = n.get("link")
            if not link or link in seen:
                continue
            seen.add(link)
            out.append({"region": gl, "query": q, "title": n.get("title"), "link": link, "snippet": n.get("snippet"),
                        "source": n.get("source"), "date": n.get("date")})
    note = _offset_note(win)
    return {"window_note": note, "items": out} if note else out


SEARCH_QUERIES = [  # (truy vấn, gl, hl, tham số thêm)
    # Câu hỏi tự nhiên bằng tiếng Anh: Google hay hiện khối "People Also Ask" + "Related searches" cho dạng này.
    ("how much VRAM do I need to run LLM locally with Ollama", "us", "en", {}),
    ("Ollama OR \"LM Studio\" OR llama.cpp tutorial OR \"case study\" OR \"release notes\"", "us", "en", {"tbs": "qdr:w"}),
    ("chạy AI local trên laptop cần bao nhiêu VRAM hướng dẫn", "vn", "vi", {}),
    ("\"local LLM\" (site:reddit.com OR site:news.ycombinator.com OR site:discuss.huggingface.co)", "us", "en", {"tbs": "qdr:w"}),
    ("how to build AI agent with local LLM vs cloud API cost", "us", "en", {}),
]


def search(win):
    if _skip_serper():
        return _skip_serper()
    seen, results, questions, related = set(), [], [], []
    for q, gl, hl, extra in SEARCH_QUERIES:
        j = serper("search", {"q": q, "gl": gl, "hl": hl, "num": 10, **extra})
        kind = "forum" if "site:" in q else "web"
        for n in j.get("organic") or []:
            link = n.get("link")
            if not link or link in seen:
                continue
            seen.add(link)
            results.append({"kind": kind, "region": gl, "query": q, "title": n.get("title"), "link": link,
                            "snippet": n.get("snippet"), "date": n.get("date")})
        for p in j.get("peopleAlsoAsk") or []:
            questions.append({"region": gl, "query": q, "question": p.get("question"),
                              "snippet": p.get("snippet"), "link": p.get("link"), "title": p.get("title")})
        for s in j.get("relatedSearches") or []:
            related.append({"region": gl, "query": s.get("query") if isinstance(s, dict) else s})
    out = {"results": results, "people_also_ask": questions, "related_searches": related}
    if _offset_note(win):
        out["window_note"] = _offset_note(win)
    return out


AUTOCOMPLETE_SEEDS = [("chạy ai local ", "vn", "vi"), ("ollama ", "vn", "vi"),
                      ("ollama ", "us", "en"), ("vibe coding ", "us", "en")]


def autocomplete(win):
    if _skip_serper():
        return _skip_serper()
    out = []
    for q, gl, hl in AUTOCOMPLETE_SEEDS:
        j = serper("autocomplete", {"q": q, "gl": gl, "hl": hl})
        sug = [s.get("value") if isinstance(s, dict) else s for s in (j.get("suggestions") or [])]
        out.append({"seed": q.strip(), "region": gl, "suggestions": sug})
    return out


# ---------- SerpAPI (Trends + transcript) ----------
def key():
    return os.getenv("SERPAPI_KEY")


def serp(params):
    u = _load()
    budget = int(os.getenv("SERPAPI_MONTHLY_BUDGET", "250"))
    if u["used"] >= budget:
        raise OutOfBudget(f"SerpAPI: đã dùng {u['used']}/{budget} search tháng này, dừng")
    r = requests.get("https://serpapi.com/search", params={**params, "api_key": key()}, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"SerpAPI {r.status_code}: {r.text[:160]}")
    u["used"] += 1
    _save(u)
    return r.json()


def _skip():
    return {"skipped": "thiếu SERPAPI_KEY"} if not key() else None


def trends(win):
    if _skip():
        return _skip()
    out = {"window": f"{win['start']} {win['end']}"}
    kw = "ollama,local llm,vibe coding,chatgpt,claude"
    # 1) Độ quan tâm tại Việt Nam trong đúng cửa sổ tuần (giá trị tương đối, 100 = đỉnh của nhóm từ khóa).
    j = serp({"engine": "google_trends", "q": kw, "geo": "VN", "date": f"{win['start']} {win['end']}",
              "data_type": "TIMESERIES", "hl": "vi"})
    rows = (j.get("interest_over_time") or {}).get("timeline_data", [])
    out["interest_vn_week"] = [{"date": r.get("date"), "values": {v.get("query"): v.get("extracted_value") for v in r.get("values", [])}}
                               for r in rows]
    # 2) Nền 3 tháng để so sánh xu hướng.
    j = serp({"engine": "google_trends", "q": kw, "geo": "VN", "date": "today 3-m", "data_type": "TIMESERIES", "hl": "vi"})
    rows = (j.get("interest_over_time") or {}).get("timeline_data", [])
    out["interest_vn_3m"] = [{"date": r.get("date"), "values": {v.get("query"): v.get("extracted_value") for v in r.get("values", [])}}
                             for r in rows[-14:]]
    # 3) Truy vấn đang tăng quanh "local llm" tại VN trong tuần.
    j = serp({"engine": "google_trends", "q": "local llm", "geo": "VN", "date": f"{win['start']} {win['end']}",
              "data_type": "RELATED_QUERIES", "hl": "vi"})
    rq = j.get("related_queries") or {}
    out["related_rising"] = [{"query": x.get("query"), "value": x.get("value")} for x in (rq.get("rising") or [])[:20]]
    out["related_top"] = [{"query": x.get("query"), "value": x.get("value")} for x in (rq.get("top") or [])[:20]]
    return out


def transcript(video_id, lang="vi"):
    """Lấy transcript một video (1 search SerpAPI), lưu vào data/transcripts/<id>.json."""
    if not re.fullmatch(r"[\w-]{6,20}", video_id):
        raise ValueError("video id không hợp lệ")
    j = serp({"engine": "youtube_video_transcript", "v": video_id, "language_code": lang})
    segs = j.get("transcript") or []
    if not segs and "other language or auto-generated" in str(j.get("error", "")):
        # Video không có phụ đề đúng ngôn ngữ: thử lại một lần với phụ đề tự động (asr), tốn thêm 1 search.
        j = serp({"engine": "youtube_video_transcript", "v": video_id, "language_code": lang, "type": "asr"})
        segs = j.get("transcript") or []
    text = " ".join((s.get("snippet") or "").strip() for s in segs)[:15000]
    res = {"video_id": video_id, "language": lang, "segments": len(segs), "text": text,
           "error": j.get("error"), "note": "Nội dung của người khác: chỉ dùng làm tư liệu, viết lại bằng lời mới và ghi nguồn."}
    d = ROOT / "data" / "transcripts"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{video_id}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res
