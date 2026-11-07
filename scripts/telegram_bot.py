"""Bot Telegram duyệt bài.
  python scripts/telegram_bot.py send        # gửi các nháp trong pending kèm nút
  python scripts/telegram_bot.py poll        # chạy liên tục, nhận bấm nút / phản hồi sửa
  python scripts/telegram_bot.py notify "tin" # gửi một tin nhắn thường
Nút: Duyệt -> approved, Bỏ -> rejected, Sửa -> bạn trả lời tin nhắn bằng yêu cầu sửa, lưu vào feedback.
Đã đăng xong: gõ /posted <id> để chuyển sang posted (agent dùng cho báo cáo).
Chỉ chấp nhận chat có id trong TELEGRAM_CHAT_ID.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
TOKEN, CHAT = os.environ["TELEGRAM_BOT_TOKEN"], str(os.environ["TELEGRAM_CHAT_ID"])
API = f"https://api.telegram.org/bot{TOKEN}"
Q = ROOT / "data" / "queue"
for d in ("pending", "approved", "rejected", "posted", "sent"):
    (Q / d).mkdir(parents=True, exist_ok=True)
FEEDBACK = ROOT / "data" / "feedback.jsonl"
OFFSET = ROOT / "data" / ".tg_offset"
WAIT = ROOT / "data" / ".tg_waiting"


def call(method, **kw):
    r = requests.post(f"{API}/{method}", json=kw, timeout=40)
    r.raise_for_status()
    return r.json()["result"]


def render(d):
    head = f"[{d.get('type','post')}] {d['id']} | {d.get('pillar', d.get('category',''))} | rủi ro: {d.get('risk','?')}"
    if d.get("type") == "reply":
        opts = "\n\n".join(f"Phương án {i+1}:\n{t}" for i, t in enumerate(d.get("reply_options", [])))
        body = f"Comment của {d.get('author','?')}: {d.get('comment_text','')}\n\n{opts}"
    else:
        body = d["caption"] + (f"\n\n--- Phương án B ---\n{d['caption_alt']}" if d.get("caption_alt") else "")
        body += f"\n\nẢnh: {d.get('image_prompt','')}"
    src = "\n".join(d.get("sources", []))
    return f"{head}\n\n{body}\n\nNguồn:\n{src}\nQA: {d.get('qa_notes','')}"[:4000]


def send():
    for f in sorted((Q / "pending").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        kb = {"inline_keyboard": [[
            {"text": "Duyệt", "callback_data": f"ok:{d['id']}"},
            {"text": "Sửa", "callback_data": f"edit:{d['id']}"},
            {"text": "Bỏ", "callback_data": f"no:{d['id']}"}]]}
        call("sendMessage", chat_id=CHAT, text=render(d), reply_markup=kb)
        shutil.move(str(f), Q / "sent" / f.name)  # tránh gửi lặp; trạng thái do callback cập nhật
        print("đã gửi", d["id"])


def find(id_):
    for folder in ("sent", "pending"):
        p = Q / folder / f"{id_}.json"
        if p.exists():
            return p
    return None


def move(id_, dest, extra=None):
    p = find(id_)
    if not p:
        return False
    d = json.loads(p.read_text(encoding="utf-8"))
    d["status"] = dest
    d.update(extra or {})
    out = Q / dest / p.name
    out.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    p.unlink()
    return True


def poll():
    offset = int(OFFSET.read_text()) if OFFSET.exists() else 0
    awaiting = {}  # (giữ cho tương thích) message_id -> id bài
    waiting = WAIT.read_text().strip() if WAIT.exists() else None  # bài đang chờ bạn gõ phản hồi
    print("đang lắng nghe…")
    while True:
        try:
            updates = call("getUpdates", offset=offset, timeout=30)
        except requests.RequestException as e:
            print("lỗi mạng:", e)
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            OFFSET.write_text(str(offset))
            if "callback_query" in u:
                cq = u["callback_query"]
                if str(cq["message"]["chat"]["id"]) != CHAT:
                    continue
                act, _, id_ = cq["data"].partition(":")
                call("answerCallbackQuery", callback_query_id=cq["id"])
                if act == "ok" and move(id_, "approved"):
                    call("sendMessage", chat_id=CHAT, text=f"Đã duyệt {id_}. Sau khi đăng xong gõ /posted {id_}")
                elif act == "no" and move(id_, "rejected"):
                    call("sendMessage", chat_id=CHAT, text=f"Đã bỏ {id_}. Gõ lý do ở tin kế tiếp (giúp agent học).")
                    waiting = id_
                    WAIT.write_text(id_)
                elif act == "edit":
                    call("sendMessage", chat_id=CHAT, text=f"Gõ yêu cầu sửa cho {id_} ở tin kế tiếp.")
                    waiting = id_
                    WAIT.write_text(id_)
            elif "message" in u:
                m = u["message"]
                if str(m["chat"]["id"]) != CHAT:
                    continue
                text = m.get("text", "")
                if text.startswith("/posted"):
                    id_ = text.split(maxsplit=1)[1] if " " in text else ""
                    p = Q / "approved" / f"{id_}.json"
                    if p.exists():
                        d = json.loads(p.read_text(encoding="utf-8"))
                        d["status"] = "posted"
                        d["posted_ts"] = time.time()
                        (Q / "posted" / p.name).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
                        p.unlink()
                        call("sendMessage", chat_id=CHAT, text=f"Đã ghi nhận đã đăng {id_}")
                    else:
                        call("sendMessage", chat_id=CHAT, text=f"Không thấy {id_} trong danh sách đã duyệt")
                elif text and not text.startswith("/"):
                    # Nhận tin thường làm phản hồi: ưu tiên tin được "reply", nếu không thì bài đang chờ phản hồi gần nhất.
                    rid = m.get("reply_to_message", {}).get("message_id")
                    id_ = awaiting.pop(rid, None) if rid in awaiting else waiting
                    if id_:
                        with FEEDBACK.open("a", encoding="utf-8") as fh:
                            fh.write(json.dumps({"id": id_, "feedback": text, "ts": time.time()}, ensure_ascii=False) + "\n")
                        waiting = None
                        WAIT.unlink(missing_ok=True)
                        call("sendMessage", chat_id=CHAT, text=f"Đã ghi phản hồi cho {id_}. Agent đọc lại trong data/feedback.jsonl khi soạn lần sau.")
                    else:
                        call("sendMessage", chat_id=CHAT, text="Mình là bot duyệt bài, không trả lời hội thoại được. Hãy bấm nút Duyệt/Sửa/Bỏ trên bài, rồi gõ lý do ở tin kế tiếp. Lệnh: /posted <id>")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "send":
        send()
    elif cmd == "poll":
        poll()
    elif cmd == "notify":
        call("sendMessage", chat_id=CHAT, text=" ".join(sys.argv[2:])[:4000])
    else:
        print(__doc__)
