"""Kiểm tra agent đã tạo đủ sản phẩm trước khi đồng bộ lên Supabase (tránh đẩy dữ liệu dở dang).
  python scripts/cloud_verify.py [--week YYYY-MM-DD]
Cửa sổ = tuần Thứ Hai..Chủ nhật vừa kết thúc (hoặc tuần bắt đầu ở --week). Kỳ vọng: chủ đề, báo cáo, kế hoạch tuần kế tiếp.
Chỉ in kết quả đạt/lỗi, không in nội dung.
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.getenv("PROJECT_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("PROJECT_ROOT", str(ROOT))
from collect_sources import week_window  # noqa: E402


def main():
    a = sys.argv[1:]
    monday = dt.date.fromisoformat(a[a.index("--week") + 1]) if "--week" in a else None
    w = week_window(monday=monday)
    label, plan_date = w["label"], (w["start"] + dt.timedelta(days=7)).isoformat()
    checks = {
        f"data/weekly/{label}/_window.json": None,
        f"data/topics/{label}.json": lambda j: isinstance(j, list) and len(j) >= 5,
        f"data/plans/{plan_date}.json": lambda j: isinstance(j, dict) and len(j.get("slots", [])) >= 5,
    }
    bad = 0
    for rel, ok in checks.items():
        p = ROOT / rel
        good = p.exists()
        if good and ok:
            try:
                good = bool(ok(json.loads(p.read_text(encoding="utf-8-sig"))))
            except ValueError:
                good = False
        print(("ĐẠT " if good else "LỖI ") + rel)
        bad += 0 if good else 1
    rp = ROOT / "reports" / "weekly" / f"{label}.md"
    good = rp.exists() and rp.stat().st_size > 500
    print(("ĐẠT " if good else "LỖI ") + f"reports/weekly/{label}.md")
    bad += 0 if good else 1
    if bad:
        sys.exit(f"Thiếu {bad} sản phẩm, KHÔNG đồng bộ.")


if __name__ == "__main__":
    main()
