# tnc-group-agent

Agent vận hành group "Khai phá AI Local & AI Cloud" bằng Claude Code. Agent soạn, bạn duyệt qua Telegram, bạn tự đăng.

## Cài đặt (một lần)
1. `pip install -r requirements.txt`
2. Tạo bot qua @BotFather lấy token; lấy chat id của bạn (nhắn bot rồi mở `https://api.telegram.org/bot<TOKEN>/getUpdates`).
3. Sao chép `.env.example` thành `.env` và điền. Nguồn nào chưa có key thì để trống, script tự bỏ qua.
4. Điền các mục `[ĐIỀN]` trong `brand/brand-brain.md`.
5. Chạy thử: `python scripts/collect_sources.py`, rồi trong thư mục này gõ `claude` và chạy `/daily`.

## Nhịp chạy
- **Sáng thứ Hai** (Task Scheduler 06:30, hoặc nút "Chạy cả tuần" trên dashboard): `powershell -File scripts\run_daily.ps1 weekly`
  thu thập TẤT CẢ nguồn cho tuần trước (thứ Hai -> Chủ nhật, giờ VN) vào `data/weekly/<ngày thứ Hai>/`, lấy transcript top 10 video, rồi `/weekly`:
  chọn chủ đề, báo cáo tuần, lập kế hoạch tuần mới.
- **Hằng ngày** (07:00): `powershell -File scripts\run_daily.ps1 daily` viết caption và prompt ảnh cho slot hôm nay từ kế hoạch tuần (không gọi API tìm kiếm).
- **Ngày 1 hằng tháng**: `... run_daily.ps1 monthly`.
- Giữ một cửa sổ chạy `python scripts/telegram_bot.py poll` để nhận nút Duyệt/Sửa/Bỏ.
- Chạy bù một tuần cũ: `python scripts/collect_sources.py --week 2026-11-02` (Serper lọc tin theo 7 ngày gần nhất tính từ hôm nay nên có thể lệch).
- Chi phí mỗi tuần: khoảng 15 credit Serper + tối đa 13 search SerpAPI (3 Trends + 10 transcript).

## Vòng làm việc của bạn
Telegram nhận bài nháp → bấm Duyệt (hoặc Sửa/Bỏ kèm lý do) → copy caption, tạo ảnh từ `image_prompt`, đăng vào group → gõ `/posted <id>`.
Comment mới: dán vào `data/inbox/comments.json` rồi chạy `/reply`.

## Dashboard (không cần Telegram)
`python scripts/dashboard.py` rồi mở http://127.0.0.1:8765. Chỉ lắng nghe trên máy bạn. Có: tổng quan, duyệt bài (chọn A/B, copy, duyệt/bỏ/đã đăng), kế hoạch, chủ đề, trạng thái nguồn dữ liệu, báo cáo, nút chạy lệnh. Các nút /daily, /weekly, /monthly, /reply cần lệnh `claude` trong PATH.

## Chia sẻ báo cáo có đăng nhập (Supabase)
1. Trong Supabase: SQL Editor chạy `supabase/schema.sql` một lần. Authentication → tắt "Allow new users to sign up". Điền `SUPABASE_PROJECT_URL`, `SUPABASE_SERVICE_ROLE_KEY` vào `.env` (khóa này TUYỆT ĐỐI không đưa lên web/GitHub).
2. Kiểm tra: `python scripts/check_env.py supabase`.
3. Mời người xem: `python scripts/manage_viewers.py add email@example.com "ghi chú"` (thu hồi: `remove`).
4. Xem trước báo cáo đã lược bỏ phần nội bộ: `python scripts/publish_reports.py`, đọc kỹ rồi gửi thật: `... --publish`.
5. Trang xem: thư mục `docs/` (điền `docs/config.js` bằng URL + anon key; GitHub Pages: Source = Deploy from a branch, thư mục /docs). Đặt ở hosting tĩnh bất kỳ; thêm địa chỉ trang vào Authentication → URL Configuration → Redirect URLs.

## Bản web cho nhân viên (Supabase)
Mọi người đăng nhập vào MỘT link duy nhất: trang gốc `docs/index.html` (GitHub Pages) và dùng dashboard như bạn: xem mọi tab, sửa caption, duyệt/bỏ, đánh dấu đã đăng. Agent vẫn chạy trên máy chủ chính của bạn; nút Chạy lệnh bị ẩn trên bản web.
1. SQL Editor: chạy `supabase/schema.sql` rồi `supabase/schema_staff.sql` (một lần).
2. Nhân viên = MỌI tài khoản trong Supabase Authentication -> Users (chạy thêm `supabase/staff_any_user.sql` một lần). Thêm người: Add user -> Create new user (tick Auto Confirm). Giữ "Allow new users to sign up" TẮT. Họ đọc được TOÀN BỘ bài nháp, kế hoạch, chủ đề, báo cáo. Liệt kê/thu hồi: `python scripts/manage_staff.py list|remove`.
3. Đồng bộ: `python scripts/sync_supabase.py both` (hoặc nút "Đồng bộ lên web" trên dashboard cục bộ). `run_daily.ps1` tự đồng bộ sau mỗi lần chạy. Nên đặt thêm lịch chạy lệnh này mỗi 10-15 phút để nhận thao tác của nhân viên.
4. Sửa giao diện dashboard rồi build lại bản web: `python scripts/build_web_app.py`.
5. Thêm địa chỉ trang gốc (kết thúc bằng `/`) vào Supabase Authentication -> URL Configuration -> Redirect URLs.
Không đưa lên Supabase: .env, Brand Brain/FAQ, transcript, dữ liệu thô tuần, danh sách kênh theo dõi.

## Lưu ý
- Facebook không có API đọc/đăng group, nên phần đăng và đọc comment trong group là thủ công. Số liệu group nhập thủ công vào `data/metrics/` (xuất Insights dạng CSV). Dự án không dùng API Page, YouTube hay GA4, nên mọi số liệu đăng bài và traffic (nếu cần) đều nhập tay vào `data/metrics/`.
- Chưa có bước tự tạo ảnh: agent chỉ ra `image_prompt`. Có thể nối thêm Canva hoặc API tạo ảnh sau.
- Zalo: Zalo OA API hạn chế hơn Telegram, nên bản này duyệt qua Telegram. Có thể thêm Zalo sau.
