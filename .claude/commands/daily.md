---
description: Hằng ngày - viết caption và prompt ảnh cho slot hôm nay từ kế hoạch tuần, QA, ra hàng chờ duyệt
---
Không thu thập dữ liệu hay research mỗi ngày: dữ liệu, chủ đề và kế hoạch đã được chuẩn bị mỗi sáng thứ Hai (`/weekly`).
1. Tìm kế hoạch tuần mới nhất trong `data/plans/` và kho chủ đề mới nhất trong `data/topics/`. Nếu chưa có kế hoạch cho tuần hiện tại, báo "chưa chạy /weekly" và dừng.
2. Với các slot của HÔM NAY chưa có nháp (trong `data/queue/`), dùng subagent `content` soạn caption (2 phương án) và prompt ảnh. Truyền ngày hôm nay và đường dẫn kế hoạch/kho chủ đề. Subagent đọc cả `data/feedback.jsonl`.
3. Nếu `data/inbox/comments.json` có comment, dùng subagent `community`.
4. Dùng subagent `qa` kiểm toàn bộ nháp mới.
5. In tóm tắt: số nháp, rủi ro cao, nguồn bị loại. KHÔNG đăng gì.
