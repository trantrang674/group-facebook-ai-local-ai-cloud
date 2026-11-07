"""Lấy transcript một video YouTube qua SerpAPI (tốn 1 search).
Dùng: python scripts/fetch_transcript.py <link hoặc video_id> [mã ngôn ngữ, mặc định en]
Kết quả: data/transcripts/<video_id>.json
"""
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
import serp  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{6,20})", sys.argv[1])
vid = m.group(1) if m else sys.argv[1]
if not serp.key():
    sys.exit("Thiếu SERPAPI_KEY trong .env")
try:
    r = serp.transcript(vid, sys.argv[2] if len(sys.argv) > 2 else "en")
except Exception as e:  # noqa: BLE001
    sys.exit(f"Lỗi: {e}")
print(f"{vid}: {r['segments']} đoạn" + (f", lỗi: {r['error']}" if r["error"] else ""))
print("Đã lưu data/transcripts/%s.json" % vid)
