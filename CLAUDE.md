# Hệ thống agent vận hành group Facebook "Khai phá AI Local & AI Cloud"

Mục tiêu: xây cộng đồng chất lượng về AI Local/Cloud. Thương hiệu của chủ group xuất hiện dần theo giai đoạn (xem `brand/brand-brain.md`).

## Nguyên tắc bất biến
1. Agent KHÔNG tự đăng. Mọi bài và mọi câu trả lời chỉ ra dạng nháp vào `data/queue/pending/`. Người duyệt qua Telegram rồi tự đăng.
2. Không có số liệu nếu không có nguồn. Mọi con số (VRAM, benchmark, giá) phải ghi link nguồn trong trường `sources`.
3. Không seeding bằng tài khoản ảo. Không mời hàng loạt.
4. Giai đoạn hiện tại: đọc `brand/brand-brain.md` mục "Giai đoạn". Giai đoạn 1 = 0% bán hàng.
5. Giọng văn, từ cấm, định dạng: theo `brand/brand-brain.md`.

## Cấu trúc
- `brand/` Brand Brain, FAQ, danh sách sản phẩm.
- `data/weekly/<ngày thứ Hai>/` dữ liệu thô của CẢ TUẦN (thứ Hai..Chủ nhật tuần trước), do `scripts/collect_sources.py` thu thập mỗi sáng thứ Hai. Không còn thu thập hằng ngày.
- `data/topics/<ngày thứ Hai>.json` kho chủ đề của tuần (tối đa 20). `data/plans/<ngày thứ Hai>.json` lịch nội dung tuần. `data/transcripts/` transcript top 10 video/tuần.
- `data/queue/{pending,approved,rejected,posted}/` hàng chờ duyệt, mỗi bài một file JSON.
- `data/metrics/` số liệu đã đăng. `reports/weekly|monthly/` báo cáo.
- `.claude/agents/` research, strategist, content, community, qa, analyst.
- `.claude/commands/` `/weekly` (sáng thứ Hai: research, báo cáo, kế hoạch tuần), `/daily` (caption + prompt ảnh cho slot hôm nay), `/monthly`, `/reply`.

## Định dạng nháp (data/queue/pending/<id>.json)
```json
{"id":"2026-11-06_am_01","date":"2026-11-06","slot":"07:30","type":"post|reply",
 "pillar":"tin_ai|thu_thuat|huong_dan|thao_luan|cau_hinh|case",
 "caption":"...","image_prompt":"...","image_path":null,
 "sources":["https://..."],"risk":"low|medium|high","qa_notes":"...","status":"pending"}
```
Nháp trả lời comment thêm: `"comment_text"`, `"reply_options":["..",".."]`, `"category"`.
