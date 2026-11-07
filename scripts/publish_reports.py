"""Đẩy báo cáo tuần/tháng lên Supabase để chia sẻ có đăng nhập. MẶC ĐỊNH CHỈ XEM TRƯỚC, không gửi gì đi.

  python scripts/publish_reports.py                      # xem trước (dry-run): hiện bản đã lược bỏ + các dòng bị xóa
  python scripts/publish_reports.py --publish            # gửi thật lên Supabase
  python scripts/publish_reports.py --only weekly/2026-11-02.md [--publish]

Lược bỏ tự động trước khi gửi (bạn nên đọc bản xem trước):
  - khối nằm giữa <!-- internal --> ... <!-- /internal --> (dùng để tự đánh dấu phần nội bộ trong báo cáo)
  - dòng nhắc tới credit/Serper/SerpAPI, .env, service_role, đường dẫn data/ scripts/ logs/, feedback.jsonl, localhost
  - ID bài nháp (2026-11-05_pm_01) được đổi thành "bài ngày 05/11"
File bắt đầu bằng dấu _ bị bỏ qua.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

DROP_LINE = re.compile(r"(credits?\b|serper|serpapi|api[_ ]?key|\.env\b|service_role|\bdata/|\bscripts/|\blogs?/|feedback\.jsonl|localhost|127\.0\.0\.1)", re.I)
DRAFT_ID = re.compile(r"(?:\bbài\s+)?\b(\d{4})-(\d{2})-(\d{2})_(?:am|pm)_\d+\b", re.I)
INTERNAL = re.compile(r"<!--\s*internal\s*-->.*?<!--\s*/internal\s*-->", re.S | re.I)


def sanitize(md):
    """Trả (văn bản đã lược bỏ, danh sách phần bị xóa)."""
    removed = []
    for m in INTERNAL.finditer(md):
        removed.append("[khối internal] " + " ".join(m.group(0).split())[:120])
    md = INTERNAL.sub("", md)
    out = []
    for line in md.splitlines():
        if DROP_LINE.search(line):
            removed.append(line.strip()[:140])
            continue
        out.append(DRAFT_ID.sub(lambda m: f"bài ngày {m.group(3)}/{m.group(2)}", line))
    return "\n".join(out).strip() + "\n", removed


def collect(only=None):
    items = []
    for kind in ("weekly", "monthly"):
        for f in sorted((ROOT / "reports" / kind).glob("*.md")):
            if f.name.startswith("_"):
                continue
            if only and f"{kind}/{f.name}" != only.replace("\\", "/"):
                continue
            raw = f.read_text(encoding="utf-8-sig")
            body, removed = sanitize(raw)
            t = re.search(r"^#\s+(.+)$", body, re.M)
            items.append({"kind": kind, "period": f.stem, "title": (t.group(1).strip() if t else f"Báo cáo {f.stem}")[:200],
                          "body_md": body, "_removed": removed, "_file": f"{kind}/{f.name}"})
    return items


def main():
    args = sys.argv[1:]
    publish = "--publish" in args
    only = args[args.index("--only") + 1] if "--only" in args else None
    items = collect(only)
    if not items:
        print("Không có báo cáo nào trong reports/weekly hoặc reports/monthly.")
        return
    for it in items:
        print(f"\n=== {it['_file']} -> {it['kind']} / {it['period']} | {it['title']}")
        print(f"    {len(it['body_md'])} ký tự, đã lược bỏ {len(it['_removed'])} phần")
        for r in it["_removed"]:
            print("    - bỏ:", r)
    if not publish:
        print("\n(Chỉ xem trước. Thêm --publish để gửi lên Supabase sau khi bạn đã đọc kỹ phần bị lược bỏ và nội dung còn lại.)")
        return
    import supa
    for it in items:
        row = {k: it[k] for k in ("kind", "period", "title", "body_md")}
        supa.rest("POST", "reports?on_conflict=kind,period", json=row, hdr={"Prefer": "resolution=merge-duplicates,return=minimal"})
        print(f"Đã gửi {it['_file']}")


if __name__ == "__main__":
    main()
