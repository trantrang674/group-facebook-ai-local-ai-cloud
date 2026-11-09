"""Dashboard cục bộ cho dự án. Chạy: python scripts/dashboard.py  rồi mở http://127.0.0.1:8765
Chỉ dùng thư viện chuẩn. Chỉ lắng nghe 127.0.0.1 (không ra mạng ngoài).
"""
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / "data" / "queue"
STATUSES = ("pending", "sent", "approved", "rejected", "posted")
PORT = 8765
ID_RE = re.compile(r"^[\w.\-]+$")
ALLOWED_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "Task"]
JOB = {"name": None, "started": None, "running": False, "code": None, "log": None, "error": None}
LOCK = threading.Lock()


def rj(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def wj(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def latest(folder, pattern="*.json"):
    files = sorted((ROOT / folder).glob(pattern), key=lambda f: f.stat().st_mtime)  # mới nhất theo thời gian sửa
    return files[-1] if files else None


def drafts():
    out = []
    for st in STATUSES:
        for f in sorted((Q / st).glob("*.json")):
            try:
                d = rj(f)
            except Exception:  # noqa: BLE001
                continue
            d["_folder"] = st
            out.append(d)
    return out


def sources_status():
    d = latest("data/weekly", "*")  # thư mục tuần mới nhất, tên = ngày thứ Hai của cửa sổ
    res = {"date": d.name if d else None, "items": []}
    if not d:
        return res
    try:
        w = rj(d / "_window.json")
        res["window"] = f"{w['start']} .. {w['end']}"
        res["collected_at"] = w.get("collected_at")
    except Exception:  # noqa: BLE001
        pass
    for f in sorted(d.glob("*.json")):
        if f.name.startswith("_") or f.stem == "reddit":  # dự án không dùng Reddit
            continue
        try:
            data = rj(f)
        except Exception as e:  # noqa: BLE001
            res["items"].append({"name": f.stem, "status": "loi", "detail": str(e)})
            continue
        if isinstance(data, dict) and "error" in data:
            res["items"].append({"name": f.stem, "status": "loi", "detail": data["error"][:160]})
        elif isinstance(data, dict) and "skipped" in data:
            res["items"].append({"name": f.stem, "status": "bo_qua", "detail": data["skipped"]})
        else:
            if isinstance(data, list):
                n = len(data)
            elif isinstance(data, dict) and "results" in data:
                n = len(data["results"]) + len(data.get("people_also_ask", []))
            elif isinstance(data, dict) and "items" in data:
                n = len(data["items"])
            else:
                n = len((data or {}).get("videos", []) or [data])
            res["items"].append({"name": f.stem, "status": "ok", "detail": f"{n} mục"})
    return res


def serpapi_usage():
    try:
        u = rj(ROOT / "data" / ".serpapi_usage.json")
    except Exception:  # noqa: BLE001
        u = {}
    import os
    budget = int(os.environ.get("SERPAPI_MONTHLY_BUDGET", "250"))
    return {"month": u.get("month"), "used": u.get("used", 0), "budget": budget,
            "serper_used": u.get("serper_used", 0), "serper_total": int(os.environ.get("SERPER_TOTAL_CREDITS", "2500"))}


def state():
    topics_f, plan_f = latest("data/topics"), latest("data/plans")
    reports = []
    for kind in ("weekly", "monthly"):
        for f in sorted((ROOT / "reports" / kind).glob("*.md")):
            reports.append({"kind": kind, "name": f.name})
    fb = ROOT / "data" / "feedback.jsonl"
    feedback = []
    if fb.exists():
        for x in fb.read_text(encoding="utf-8-sig").splitlines()[-10:]:
            try:
                feedback.append(json.loads(x))
            except ValueError:
                pass  # bỏ qua dòng hỏng, không làm sập dashboard
    return {
        "now": datetime.now().isoformat(timespec="seconds"),
        "drafts": drafts(),
        "plan": rj(plan_f) if plan_f else None,
        "plan_file": plan_f.name if plan_f else None,
        "topics": {"file": topics_f.name if topics_f else None, "items": rj(topics_f) if topics_f else []},
        "sources": sources_status(),
        "serpapi": serpapi_usage(),
        "reports": reports,
        "feedback": feedback,
        "env": {"telegram": env_has("TELEGRAM_BOT_TOKEN") and env_has("TELEGRAM_CHAT_ID"),
                "claude": find_claude() is not None},
        "job": job_view(),
    }


def env_has(key):
    p = ROOT / ".env"
    if not p.exists():
        return False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return bool(line.split("=", 1)[1].strip())
    return False


def find_draft(id_):
    for st in STATUSES:
        p = Q / st / f"{id_}.json"
        if p.exists():
            return st, p
    return None, None


def draft_action(body):
    id_, act = body.get("id", ""), body.get("action")
    if not ID_RE.match(id_):
        return {"error": "id không hợp lệ"}, 400
    st, p = find_draft(id_)
    if not p:
        return {"error": "không thấy bài"}, 404
    d = rj(p)
    d.pop("_folder", None)
    dest = {"approve": "approved", "reject": "rejected", "posted": "posted", "revert": "pending", "edit": st}.get(act)
    if not dest:
        return {"error": "hành động không hợp lệ"}, 400
    if act in ("edit", "posted") and isinstance(body.get("post_url"), str):  # link bài đã đăng (chỉ http/https)
        u = body["post_url"].strip()
        if u == "" or re.match(r"^https?://\S+$", u):
            d["post_url"] = u[:500]
        else:
            return {"error": "link phải bắt đầu bằng http:// hoặc https://"}, 400
    if act in ("edit", "approve"):  # lưu chỉnh sửa caption nếu có gửi kèm
        if isinstance(body.get("caption"), str) and body["caption"] != d.get("caption"):
            d["caption"], d["edited"] = body["caption"][:20000], True
        if isinstance(body.get("caption_alt"), str) and d.get("caption_alt") is not None and body["caption_alt"] != d.get("caption_alt"):
            d["caption_alt"], d["edited"] = body["caption_alt"][:20000], True
        if act == "edit" and d.get("chosen"):  # bài đã duyệt: cập nhật bản cuối theo phương án đã chọn
            d["final_caption"] = d["caption_alt"] if d["chosen"] == "B" else d.get("caption", "")
    if act == "approve":
        v = body.get("variant", "A")
        d["chosen"] = "B" if v == "B" and d.get("caption_alt") else "A"
        d["final_caption"] = d["caption_alt"] if d["chosen"] == "B" else d.get("caption", "")
    if act == "reject" and body.get("note"):
        with (ROOT / "data" / "feedback.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": id_, "feedback": str(body["note"])[:1000], "ts": time.time()}, ensure_ascii=False) + "\n")
        d["reject_note"] = str(body["note"])[:1000]
    if act == "posted":
        d["posted_ts"] = time.time()
    if act != "edit":
        d["status"] = dest
    (Q / dest).mkdir(parents=True, exist_ok=True)
    wj(Q / dest / p.name, d)
    if Q / dest / p.name != p:
        p.unlink()
    return {"ok": True, "status": dest}, 200


def find_claude():
    """Tìm claude: biến CLAUDE_BIN, rồi PATH, rồi bản đi kèm app Claude desktop (lấy bản mới nhất)."""
    import os
    env = os.environ.get("CLAUDE_BIN")
    if env and Path(env).exists():
        return env
    exe = shutil.which("claude")
    if exe:
        return exe
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Claude-Data"
    found = list(base.glob("*/claude-code/*/*/claude.exe")) if base.exists() else []
    found.sort(key=lambda p: p.stat().st_mtime)
    return str(found[-1]) if found else None


def claude_cmd(slash):
    exe = find_claude()
    if not exe:
        return None
    return [exe, "-p", slash, "--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED_TOOLS]


def job_view():
    with LOCK:
        j = dict(JOB)
    tail = ""
    if j["log"] and Path(j["log"]).exists():
        tail = Path(j["log"]).read_text(encoding="utf-8", errors="replace")[-6000:]
    j["tail"] = tail
    j.pop("log", None)
    return j


def run_job(name):
    collect = [sys.executable, str(ROOT / "scripts" / "collect_sources.py")]
    jobs = {
        "collect": [collect],
        "sync": [[sys.executable, str(ROOT / "scripts" / "sync_supabase.py"), "both"]],
        "daily": [claude_cmd("/daily")], "weekly": [claude_cmd("/weekly")],
        "weekly_all": [collect, claude_cmd("/weekly")],  # thu thập dữ liệu tuần rồi chạy /weekly
        "monthly": [claude_cmd("/monthly")], "reply": [claude_cmd("/reply")],
    }
    if name not in jobs:
        return {"error": "job không hợp lệ"}, 400
    cmds = jobs[name]
    cmd = None if any(c is None for c in cmds) else cmds
    if cmd is None:
        return {"error": "Không tìm thấy lệnh 'claude' trong PATH. Cài Claude Code CLI hoặc chạy lệnh trong terminal."}, 400
    with LOCK:
        if JOB["running"]:
            return {"error": "Đang có lệnh chạy: " + str(JOB["name"])}, 409
        (ROOT / "logs").mkdir(exist_ok=True)
        log = ROOT / "logs" / f"dashboard-{name}-{datetime.now():%Y%m%d-%H%M%S}.log"
        JOB.update(name=name, started=datetime.now().isoformat(timespec="seconds"), running=True, code=None, log=str(log), error=None)

    def work():
        try:
            with open(log, "w", encoding="utf-8") as fh:
                code = 0
                for c in cmd:  # chạy lần lượt, dừng nếu một bước thất bại
                    fh.write(f"\n$ {' '.join(Path(x).name if i == 0 else x for i, x in enumerate(c))}\n")
                    fh.flush()
                    code = subprocess.Popen(c, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).wait()
                    if code != 0:
                        break
            with LOCK:
                JOB.update(running=False, code=code)
        except Exception as e:  # noqa: BLE001
            with LOCK:
                JOB.update(running=False, code=-1, error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}, 200


def read_report(kind, name):
    if kind not in ("weekly", "monthly") or not ID_RE.match(name):
        return {"error": "không hợp lệ"}, 400
    p = ROOT / "reports" / kind / name
    return ({"text": p.read_text(encoding="utf-8")}, 200) if p.exists() else ({"error": "không thấy"}, 404)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj, code=200, ctype="application/json; charset=utf-8"):
        b = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def host_ok(self):
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self.host_ok():
            return self.send({"error": "host"}, 403)
        path, _, qs = self.path.partition("?")
        if path == "/":
            return self.send((ROOT / "dashboard" / "index.html").read_bytes(), ctype="text/html; charset=utf-8")
        if path == "/api/state":
            return self.send(state())
        if path == "/api/report":
            q = dict(x.split("=", 1) for x in qs.split("&") if "=" in x)
            return self.send(*read_report(q.get("kind", ""), q.get("name", "")))
        self.send({"error": "not found"}, 404)

    def do_POST(self):
        if not self.host_ok() or self.headers.get("X-Dashboard") != "1":
            return self.send({"error": "forbidden"}, 403)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self.send({"error": "json"}, 400)
        if self.path == "/api/draft":
            return self.send(*draft_action(body))
        if self.path == "/api/run":
            return self.send(*run_job(body.get("job", "")))
        self.send({"error": "not found"}, 404)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print("Dashboard:", url, "(Ctrl+C để dừng)")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
