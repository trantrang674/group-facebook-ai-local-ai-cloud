"""Đồng bộ hai chiều giữa máy chủ chính (file trong data/) và Supabase, để nhân viên dùng bản web.

  python scripts/sync_supabase.py pull     # nhận thao tác của nhân viên (duyệt/sửa/bỏ/đã đăng/phản hồi) về file trên máy
  python scripts/sync_supabase.py push     # đẩy bài nháp, kế hoạch, chủ đề, trạng thái nguồn, báo cáo lên Supabase
  python scripts/sync_supabase.py both     # pull rồi push (mặc định)
  python scripts/sync_supabase.py push --dry-run   # chỉ báo sẽ đẩy gì
  Cờ: --no-drafts (không đẩy bài nháp) và --no-private (không đẩy Brand Brain/FAQ/danh sách kênh) dùng cho runner GitHub Actions.

Quy tắc xung đột (đơn giản, có chủ đích): nếu nhân viên đã sửa một bài trên web mà bạn chưa kéo về, lần push sẽ BỎ QUA bài đó
(không ghi đè công việc của nhân viên); lần pull kế tiếp kéo thay đổi về máy. Nếu bạn sửa cùng bài đó trên máy trong lúc chờ, bản của nhân viên thắng.
Bảng nhân viên KHÔNG chứa: .env, Brand Brain/FAQ, transcript, dữ liệu thô tuần, danh sách kênh. Brand Brain/FAQ/danh sách kênh chỉ vào bảng
private_files (không ai ngoài service_role đọc được) để runner GitHub Actions tải về.
pull cũng kéo về kế hoạch, chủ đề, báo cáo do runner đám mây tạo (chỉ khi file đó chưa có hoặc cũ hơn trên máy).
"""
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.getenv("PROJECT_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402

Q = ROOT / "data" / "queue"
FOLDERS = ("pending", "sent", "approved", "rejected", "posted")
STATE = ROOT / "data" / ".sync_state.json"
COLS = ("id", "date", "slot", "type", "pillar", "caption", "caption_alt", "image_prompt", "sources", "risk", "qa_notes",
        "chosen", "final_caption", "edited", "post_url", "reject_note")
PULL_COLS = ("caption", "caption_alt", "chosen", "final_caption", "edited", "post_url", "reject_note")


def rj(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def wj(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def iso_mtime(p):
    return dt.datetime.fromtimestamp(Path(p).stat().st_mtime, dt.timezone.utc).isoformat()


def local_drafts():
    out = {}
    for f in FOLDERS:
        for p in sorted((Q / f).glob("*.json")):
            try:
                d = rj(p)
            except Exception:  # noqa: BLE001
                continue
            out[d.get("id", p.stem)] = (f, p, d)
    return out


def draft_row(folder, d):
    row = {k: d.get(k) for k in COLS if k in d}
    row["folder"] = folder
    row["sources"] = d.get("sources") or []
    row["edited"] = bool(d.get("edited"))
    row["extra"] = {k: v for k, v in d.items() if k not in COLS and k not in ("status", "_folder")}
    for k in ("caption", "date", "slot"):
        row[k] = d.get(k) or ""
    for k in COLS:  # PostgREST yêu cầu mọi dòng trong một lần gửi có CÙNG tập khóa
        row.setdefault(k, None)
    row["type"] = d.get("type") or "post"
    return row


def pull(dry=False):
    rows = supa.rest("GET", "drafts", params={"select": "*", "updated_by": "neq.local"}).json()
    local = local_drafts()
    applied = 0
    for r in rows:
        cur = local.get(r["id"])
        d = dict(cur[2]) if cur else {"id": r["id"], "date": r["date"], "slot": r["slot"], "type": r.get("type") or "post",
                                       "pillar": r.get("pillar"), "image_prompt": r.get("image_prompt"), "sources": r.get("sources") or [],
                                       "risk": r.get("risk"), "qa_notes": r.get("qa_notes")}
        for k in PULL_COLS:
            if r.get(k) is not None or k in ("post_url", "reject_note"):
                d[k] = r.get(k)
        d["status"] = "pending" if r["folder"] in ("pending", "sent") else r["folder"]
        d["by_web"] = r.get("updated_by")
        print(f"  nhận {r['id']}: {cur[0] if cur else '(mới)'} -> {r['folder']} (bởi {r.get('updated_by')})")
        if dry:
            continue
        wj(Q / r["folder"] / f"{r['id']}.json", d)
        if cur and cur[1] != Q / r["folder"] / f"{r['id']}.json":
            cur[1].unlink(missing_ok=True)
        # xác nhận đã nhận: trả quyền sở hữu về 'local' (chỉ khi chưa bị sửa tiếp: lọc theo updated_at)
        ack = supa.rest("PATCH", "drafts", params={"id": f"eq.{r['id']}", "updated_at": f"eq.{r['updated_at']}"},
                        json={"edited": bool(r.get("edited"))}, hdr={"Prefer": "return=representation"}).json()
        if not ack:
            print("    (nhân viên vừa sửa tiếp, sẽ nhận ở lần pull sau)")
        applied += 1
    # phản hồi do nhân viên gửi -> data/feedback.jsonl để agent đọc
    fb = supa.rest("GET", "feedback", params={"select": "id,draft_id,feedback,created_by,created_at", "source": "eq.web", "synced": "eq.false", "order": "id"}).json()
    if fb and not dry:
        with (ROOT / "data" / "feedback.jsonl").open("a", encoding="utf-8") as fh:
            for x in fb:
                fh.write(json.dumps({"id": x["draft_id"], "feedback": x["feedback"], "ts": time.time(), "by": x["created_by"]}, ensure_ascii=False) + "\n")
        supa.rest("PATCH", "feedback", params={"id": "in.(" + ",".join(str(x["id"]) for x in fb) + ")"}, json={"synced": True})
    print(f"pull xong: {applied} bài từ nhân viên, {len(fb)} phản hồi")


def pull_cloud(dry=False):
    """Kéo kế hoạch, chủ đề, báo cáo do runner đám mây tạo về máy (không ghi đè file local mới hơn)."""
    n = 0
    for table, key, folder, ext in (("plans", "week", "plans", ".json"), ("topics", "file", "topics", ".json")):
        for r in supa.rest("GET", table, params={"select": "*"}).json():
            dest = ROOT / "data" / folder / f"{r[key]}{ext}"
            remote_t = dt.datetime.fromisoformat(r["src_mtime"].replace("Z", "+00:00")).timestamp()
            if dest.exists() and dest.stat().st_mtime + 2 >= remote_t:
                continue
            data = r.get("raw") if table == "plans" else r.get("items")
            if table == "plans" and not data:
                data = {"week": r["week"], "range": r.get("range"), "notes": r.get("notes"), "slots": r["slots"], "trial_today": r.get("trial_today") or []}
            print(f"  nhận {table}: {dest.name}")
            n += 1
            if not dry:
                wj(dest, data)
                os.utime(dest, (remote_t, remote_t))  # giữ mtime gốc để lần push sau không coi là bản mới
    for r in supa.rest("GET", "reports_internal", params={"select": "kind,period,body_md"}).json():
        dest = ROOT / "reports" / r["kind"] / f"{r['period']}.md"
        if dest.exists():
            continue
        print(f"  nhận báo cáo: {r['kind']}/{dest.name}")
        n += 1
        if not dry:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(r["body_md"], encoding="utf-8")
    print(f"pull_cloud xong: {n} mục từ runner đám mây")


def push(dry=False, drafts=True, private=True):
    from dashboard import sources_status  # tái dùng cách tính trạng thái nguồn của dashboard

    state = {}
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if drafts:
        remote = {r["id"]: r for r in supa.rest("GET", "drafts", params={"select": "id,updated_by"}).json()}
        local = local_drafts()
        rows, skipped = [], 0
        for id_, (folder, _p, d) in local.items():
            if remote.get(id_, {}).get("updated_by", "local") != "local":
                skipped += 1  # nhân viên đã sửa, chờ pull
                continue
            rows.append(draft_row(folder, d))
        print(f"bài nháp: đẩy {len(rows)}, bỏ qua {skipped} (chờ nhận thay đổi của nhân viên)")
        if not dry and rows:
            supa.rest("POST", "drafts?on_conflict=id", json=rows, hdr={"Prefer": "resolution=merge-duplicates,return=minimal"})
    else:
        print("bài nháp: bỏ qua (--no-drafts)")

    plans = []
    for p in sorted((ROOT / "data" / "plans").glob("*.json")):
        j = rj(p)
        plans.append({"week": p.stem, "range": j.get("range"), "notes": j.get("notes"), "slots": j.get("slots") or [],
                      "trial_today": j.get("trial_today") or [], "raw": j, "src_mtime": iso_mtime(p)})
    topics = [{"file": p.stem, "items": rj(p), "src_mtime": iso_mtime(p)} for p in sorted((ROOT / "data" / "topics").glob("*.json"))]
    reports = []
    for kind in ("weekly", "monthly"):
        for p in sorted((ROOT / "reports" / kind).glob("*.md")):
            if p.name.startswith("_"):
                continue
            body = p.read_text(encoding="utf-8-sig")
            title = next((ln.lstrip("# ").strip() for ln in body.splitlines() if ln.startswith("#")), f"Báo cáo {p.stem}")
            reports.append({"kind": kind, "period": p.stem, "title": title[:200], "body_md": body})
    src = sources_status()
    runs = [{"week": src["date"], "window": src.get("window"), "collected_at": src.get("collected_at"), "items": src["items"]}] if src.get("date") else []
    print(f"kế hoạch {len(plans)}, chủ đề {len(topics)}, báo cáo {len(reports)}, lượt quét nguồn {len(runs)}")
    if dry:
        return
    for table, data, conflict in (("plans", plans, "week"), ("topics", topics, "file"), ("source_runs", runs, "week"),
                                  ("reports_internal", reports, "kind,period")):
        if data:
            supa.rest("POST", f"{table}?on_conflict={conflict}", json=data, hdr={"Prefer": "resolution=merge-duplicates,return=minimal"})
    # phản hồi cục bộ (Telegram/dashboard) -> để nhân viên xem
    fbp = ROOT / "data" / "feedback.jsonl"
    lines = [ln for ln in fbp.read_text(encoding="utf-8-sig").splitlines() if ln.strip()] if fbp.exists() else []
    done = int(state.get("feedback_pushed", 0))
    new = []
    for ln in lines[done:]:
        try:
            x = json.loads(ln)
            new.append({"draft_id": x.get("id"), "feedback": x.get("feedback", ""), "source": "local", "synced": True})
        except ValueError:
            pass
    if new:
        supa.rest("POST", "feedback", json=new, hdr={"Prefer": "return=minimal"})
    if private:
        files = [ROOT / "brand" / "brand-brain.md", ROOT / "brand" / "faq.md", ROOT / "config" / "youtube_channels.txt"]
        up = [{"path": f.relative_to(ROOT).as_posix(), "content": f.read_text(encoding="utf-8-sig")} for f in files if f.exists()]
        if up:
            try:
                supa.rest("POST", "private_files?on_conflict=path", json=up, hdr={"Prefer": "resolution=merge-duplicates,return=minimal"})
                print(f"file riêng tư (chỉ service_role đọc được): {len(up)} file")
            except RuntimeError as e:
                print("Chưa đẩy được file riêng tư (đã chạy supabase/cloud_pipeline.sql chưa?):", str(e)[:120])
    state["feedback_pushed"] = len(lines)
    state["last_push"] = dt.datetime.now(dt.timezone.utc).isoformat()
    wj(STATE, state)
    print("push xong")


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else "both"
    dry = "--dry-run" in a
    if cmd in ("pull", "both"):
        pull(dry)
        pull_cloud(dry)
    if cmd in ("push", "both"):
        push(dry, drafts="--no-drafts" not in a, private="--no-private" not in a)
    if cmd not in ("pull", "push", "both"):
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
