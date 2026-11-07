---
description: Chạy vào sáng thứ Hai - chọn chủ đề từ dữ liệu tuần trước, báo cáo tuần, lập kế hoạch tuần mới
---
Quy trình đầu tuần. Dữ liệu thô của tuần trước (thứ Hai -> Chủ nhật) đã được thu thập sẵn bằng `scripts/collect_sources.py` vào `data/weekly/<ngày thứ Hai>/`. Dùng thư mục tuần mới nhất. Nếu không có, báo lỗi và dừng (không tự thu thập).
1. Dùng subagent `research` tạo `data/topics/<ngày thứ Hai của cửa sổ>.json` từ dữ liệu tuần và transcript video.
2. Dùng subagent `analyst` viết báo cáo tuần vừa qua vào `reports/weekly/<ngày thứ Hai của cửa sổ>.md` (dựa trên bài đã đăng trong `data/queue/posted/` và `data/metrics/`; nếu chưa có số liệu thì nói rõ "chưa đủ dữ liệu").
3. Dùng subagent `strategist` lập kế hoạch cho tuần mới (thứ Hai ngay sau cửa sổ -> Chủ nhật) vào `data/plans/<ngày thứ Hai tuần mới>.json`, dùng kho chủ đề vừa tạo và áp dụng các đề xuất đã `APPROVED`.
4. Cập nhật `brand/faq.md` với các câu hỏi lặp lại (chỉ thêm mục có nguồn, đánh dấu `[CHỜ DUYỆT]`) nếu `faq.md` đang được dùng.
5. In tóm tắt 10 dòng: số chủ đề, ai kênh/video nổi bật, kế hoạch tuần mới, những gì còn thiếu. KHÔNG đăng gì.
