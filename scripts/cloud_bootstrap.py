"""Chuẩn bị môi trường cho runner GitHub Actions: tải dữ liệu riêng tư từ Supabase (repo công khai không chứa chúng).

  python scripts/cloud_bootstrap.py                 # tải Brand Brain, FAQ, danh sách kênh, phản hồi, bài nháp, báo cáo/kế hoạch/chủ đề gần đây
  python scripts/cloud_bootstrap.py --upload-state  # sau khi chạy xong: đẩy bộ đếm lượt API lên để lần chạy sau (và máy bạn) biết đã dùng bao nhiêu

CHỈ IN SỐ LƯỢNG, không in nội dung (nhật ký Actions của repo công khai ai cũng đọc được).
Biến PROJECT_ROOT (tùy chọn) đổi thư mục đích, dùng để chạy thử không đụng dữ liệu thật.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.getenv("PROJECT_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402

ALLOWED = ("brand/", "config/", "data/.serpapi_usage.json")   # chỉ ghi vào các đường dẫn này từ private_files
REQUIRED = ("brand/brand-brain.md",)
FOLDERS = ("pending", "sent", "approved", "rejected", "posted")


def safe_dest(path):
    if ".." in Path(path).parts or Path(path).is_absolute() or not path.startswith(ALLOWED):
        raise SystemExit(f"Đường dẫn không hợp lệ trong private_files: {path[:60]}")
    return ROOT / path


def wj(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def download():
    n = 0
    try:
        for r in supa.rest("GET", "private_files", params={"select": "path,content"}).json():
            dest = safe_dest(r["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(r["content"], encoding="utf-8")
            n += 1
    except RuntimeError as e:
        print("Không đọc được private_files (đã chạy supabase/cloud_pipeline.sql và sync_supabase.py push trên máy bạn chưa?):", str(e)[:100])
    print(f"file riêng tư: {n}")

    fb = supa.rest("GET", "feedback", params={"select": "draft_id,feedback,created_by", "order": "id"}).json()
    fp = ROOT / "data" / "feedback.jsonl"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("".join(json.dumps({"id": x["draft_id"], "feedback": x["feedback"], "by": x["created_by"]}, ensure_ascii=False) + "\n" for x in fb), encoding="utf-8")
    # đánh dấu đã có sẵn để push không lặp lại các dòng này
    wj(ROOT / "data" / ".sync_state.json", {"feedback_pushed": len(fb)})
    print(f"phản hồi: {len(fb)}")

    drafts = supa.rest("GET", "drafts", params={"select": "*"}).json()
    for r in drafts:
        d = {k: r.get(k) for k in ("id", "date", "slot", "type", "pillar", "caption", "caption_alt", "image_prompt", "sources", "risk",
                                    "qa_notes", "chosen", "final_caption", "edited", "post_url", "reject_note")}
        d.update(r.get("extra") or {})
        d["status"] = "pending" if r["folder"] in ("pending", "sent") else r["folder"]
        wj(ROOT / "data" / "queue" / r["folder"] / f"{r['id']}.json", d)
    print(f"bài nháp (để báo cáo biết bài nào đã đăng): {len(drafts)}")

    n = 0
    for r in supa.rest("GET", "reports_internal", params={"select": "kind,period,body_md", "order": "period.desc", "limit": 8}).json():
        dest = ROOT / "reports" / r["kind"] / f"{r['period']}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(r["body_md"], encoding="utf-8")
        n += 1
    print(f"báo cáo gần đây: {n}")
    n = 0
    for r in supa.rest("GET", "plans", params={"select": "*", "order": "src_mtime.desc", "limit": 3}).json():
        wj(ROOT / "data" / "plans" / f"{r['week']}.json", r.get("raw") or {"week": r["week"], "range": r.get("range"), "notes": r.get("notes"), "slots": r["slots"]})
        n += 1
    for r in supa.rest("GET", "topics", params={"select": "*", "order": "src_mtime.desc", "limit": 2}).json():
        wj(ROOT / "data" / "topics" / f"{r['file']}.json", r["items"])
        n += 1
    print(f"kế hoạch/chủ đề gần đây: {n}")

    missing = [f for f in REQUIRED if not (ROOT / f).exists()]
    if missing:
        raise SystemExit("Thiếu file bắt buộc: " + ", ".join(missing) + ". Chạy 'python scripts/sync_supabase.py push' trên máy bạn để tải lên.")


def upload_state():
    f = ROOT / "data" / ".serpapi_usage.json"
    if f.exists():
        supa.rest("POST", "private_files?on_conflict=path", json=[{"path": "data/.serpapi_usage.json", "content": f.read_text(encoding="utf-8")}],
                  hdr={"Prefer": "resolution=merge-duplicates,return=minimal"})
        print("đã lưu bộ đếm lượt API")


if __name__ == "__main__":
    upload_state() if "--upload-state" in sys.argv else download()
