"""Tạo bản web của dashboard: docs/index.html = dashboard/index.html + lớp dữ liệu Supabase (dashboard/remote_layer.js).
Chạy lại mỗi khi sửa giao diện dashboard/index.html:  python scripts/build_web_app.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "dashboard" / "index.html"
LAYER = ROOT / "dashboard" / "remote_layer.js"
OUT = ROOT / "docs" / "index.html"   # MỘT link duy nhất (trang gốc) cho mọi người đăng nhập
CDN = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"


GATE_CSS = """#gate{position:fixed;inset:0;z-index:50;display:none;align-items:center;justify-content:center;padding:16px;overflow:auto;
 background:linear-gradient(135deg,#e9eefb,#d8dff2 60%,#e6ebf7);--lgbox:#fff;--lginp:#eaf0ff;--lgln:#cfd8f3}
@media(prefers-color-scheme:dark){#gate{background:linear-gradient(135deg,#0a1226,#0d1730 60%,#0a1226);--lgbox:#121c36;--lginp:#182a57;--lgln:#24335a}}
.lg{width:100%;max-width:450px;text-align:center}
.lg .logo{width:64px;height:64px;border-radius:18px;background:#fff;color:var(--navy);box-shadow:0 6px 20px rgba(15,40,110,.18);margin:0 auto 18px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.3rem}
.lg h1{font-size:1.65rem;margin:0;letter-spacing:.3px;color:var(--tx);background:none;-webkit-text-fill-color:currentColor}.lg h1 em{color:var(--or1);font-style:normal}
.lg .sub{color:var(--mut);font-size:.9rem;margin:6px 0 22px}
.lg .box{background:var(--lgbox);border-radius:18px;padding:24px;text-align:left;box-shadow:0 10px 30px rgba(15,40,110,.14)}
.lg label{display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:.88rem;margin:0 0 6px}
.lg input{width:100%;padding:13px 14px;border:1px solid var(--lgln);border-radius:12px;background:var(--lginp);font:inherit;color:var(--tx)}
.lg .pw{position:relative}.lg .pw input{padding-right:44px}.lg .pw button{position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:0;cursor:pointer;font-size:1.05rem;opacity:.7}
.lg .go{width:100%;margin-top:18px;padding:14px;border:0;border-radius:12px;color:#fff;font:700 1rem system-ui,sans-serif;background:linear-gradient(90deg,var(--navy),var(--ac));box-shadow:0 8px 20px rgba(31,86,224,.3);cursor:pointer}
.lg .go:disabled{opacity:.6;cursor:not-allowed}
.lg a.fg{font-weight:500;font-size:.82rem;color:var(--ac);cursor:pointer;text-decoration:underline}
.lg .foot{font-size:.78rem;color:var(--mut);margin-top:18px}
.lg .err{margin-top:12px;padding:9px 12px;border-radius:10px;background:var(--bads);color:var(--bad);font-size:.88rem}
.lg .okm{margin-top:12px;padding:9px 12px;border-radius:10px;background:var(--oks);color:var(--ok);font-size:.88rem}
.lg .muted{color:var(--mut)}"""

def must_replace(text, old, new, label):
    if old not in text:
        raise SystemExit(f"Không tìm thấy mốc '{label}' trong dashboard/index.html, kiểm tra lại build_web_app.py")
    return text.replace(old, new, 1)


def main():
    html = SRC.read_text(encoding="utf-8")
    layer = LAYER.read_text(encoding="utf-8")
    html = must_replace(html, "<title>Group Dashboard</title>",
                        '<title>Dashboard nhân viên</title>\n<meta name="robots" content="noindex,nofollow">', "title")
    html = must_replace(html, "</style>",
                        GATE_CSS + "\n</style>", "style")
    html = must_replace(html, '<div class="app">', '<div id="gate"></div>\n<div class="app">', "app")
    html = must_replace(html, "<script>\nvar TABS=",
                        f'<script src="{CDN}"></script>\n<script src="config.js"></script>\n<script>\nvar TABS=', "script đầu")
    html = must_replace(html, "\nload();\nsetInterval(", "\n" + layer + "\nstartRemote();\nsetInterval(", "load()")
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"Đã tạo {OUT} ({len(html)} ký tự)")


if __name__ == "__main__":
    main()
