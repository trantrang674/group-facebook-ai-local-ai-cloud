"""Tạo trang HTML để duyệt bài: reports/review.html
Dùng: python scripts/build_review.py   (rồi mở reports/review.html)
Đọc các nháp trong data/queue/{pending,sent,approved}. Có nút Copy cho từng caption và prompt ảnh.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / "data" / "queue"
OUT = ROOT / "reports" / "review.html"
LABEL = {"pending": "Chờ duyệt", "sent": "Đã gửi Telegram", "approved": "Đã duyệt"}
PILLAR = {"tin_ai": "Tin AI", "thu_thuat": "Thủ thuật", "huong_dan": "Hướng dẫn",
          "thao_luan": "Thảo luận", "cau_hinh": "Cấu hình", "case": "Case"}


def esc(s):
    return html.escape(str(s or ""))


def block(title, text):
    return f"""<div class="blk"><div class="bh"><span>{esc(title)}</span>
<button type="button" onclick="cp(this)">Copy</button></div><pre>{esc(text)}</pre></div>"""


def card(d, status):
    risk = d.get("risk", "?")
    srcs = "".join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener noreferrer">{esc(u)}</a></li>'
                   for u in d.get("sources", []))
    cols = block("Phương án A", d.get("caption", ""))
    if d.get("caption_alt"):
        cols += block("Phương án B", d["caption_alt"])
    return f"""<article>
<header><h2>{esc(d['id'])}</h2>
<div class="meta"><span class="tag">{esc(LABEL.get(status, status))}</span>
<span class="tag">{esc(PILLAR.get(d.get('pillar'), d.get('pillar')))}</span>
<span class="tag r-{esc(risk)}">Rủi ro: {esc(risk)}</span>
<span class="tag">Đăng {esc(d.get('date'))} lúc {esc(d.get('slot'))}</span></div></header>
<div class="cols">{cols}</div>
{block("Prompt ảnh", d.get("image_prompt", ""))}
<details><summary>Ghi chú QA và nguồn</summary>
<p class="qa">{esc(d.get('qa_notes'))}</p><ul>{srcs}</ul></details>
</article>"""


def main():
    cards = []
    for status in ("pending", "sent", "approved"):
        for f in sorted((Q / status).glob("*.json")):
            cards.append(card(json.loads(f.read_text(encoding="utf-8")), status))
    body = "\n".join(cards) or "<p>Chưa có bài nháp nào.</p>"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(PAGE.replace("%%BODY%%", body), encoding="utf-8")
    print(f"Đã tạo {OUT} ({len(cards)} bài)")


PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Duyệt bài nháp</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--tx:#14181f;--mut:#5b6572;--ln:#dfe3e8;--ac:#0b5fff;--ok:#1a7f4b;--wn:#a15c00;--bad:#c0262d}
@media(prefers-color-scheme:dark){:root{--bg:#0f1318;--card:#171c23;--tx:#e8ecf1;--mut:#97a1ad;--ln:#2a313b;--ac:#6ea0ff;--ok:#5fd093;--wn:#f0b45a;--bad:#ff7b80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.55 system-ui,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.4rem;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 20px}
article{background:var(--card);border:1px solid var(--ln);border-radius:12px;padding:16px;margin:0 0 20px}
h2{font-size:1.05rem;margin:0 0 8px;font-family:ui-monospace,Consolas,monospace}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.tag{border:1px solid var(--ln);border-radius:999px;padding:2px 10px;font-size:.8rem;color:var(--mut)}
.r-low{color:var(--ok);border-color:var(--ok)}.r-medium{color:var(--wn);border-color:var(--wn)}.r-high{color:var(--bad);border-color:var(--bad)}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-bottom:12px}
.blk{border:1px solid var(--ln);border-radius:8px;overflow:hidden;margin-bottom:12px}.cols .blk{margin:0}
.bh{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:var(--bg);font-weight:600;font-size:.9rem}
button{font:inherit;font-size:.85rem;cursor:pointer;border:1px solid var(--ac);background:transparent;color:var(--ac);border-radius:6px;padding:2px 12px}
button:hover{background:var(--ac);color:#fff}
pre{margin:0;padding:12px;white-space:pre-wrap;word-wrap:break-word;font:inherit}
details{color:var(--mut);font-size:.9rem}summary{cursor:pointer}.qa{white-space:pre-wrap}
a{color:var(--ac);word-break:break-all}
</style></head><body><main>
<h1>Duyệt bài nháp</h1>
<p class="sub">Chọn phương án, bấm Copy, dán vào group. Ảnh tạo từ prompt bên dưới. Đăng xong thì báo lại để chuyển bài sang "posted".</p>
%%BODY%%
</main>
<script>
function cp(b){var t=b.closest('.blk').querySelector('pre').textContent;
var done=function(){var o=b.textContent;b.textContent='Đã copy';setTimeout(function(){b.textContent=o},1500)};
if(navigator.clipboard){navigator.clipboard.writeText(t).then(done,function(){fb(t,done)})}else{fb(t,done)}}
function fb(t,done){var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();
try{document.execCommand('copy');done()}catch(e){}document.body.removeChild(a)}
</script></body></html>
"""

if __name__ == "__main__":
    main()
