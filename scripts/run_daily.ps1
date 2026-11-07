# Lịch chạy (Task Scheduler):
#   Thứ Hai 06:30  : powershell -File scripts\run_daily.ps1 weekly   (thu thập dữ liệu tuần trước + /weekly)
#   Hằng ngày 07:00: powershell -File scripts\run_daily.ps1 daily    (soạn bài nháp cho slot hôm nay)
#   Ngày 1 hằng tháng: powershell -File scripts\run_daily.ps1 monthly
param([string]$Mode = "daily")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
New-Item -ItemType Directory -Force logs | Out-Null
$log = "logs\$Mode-$(Get-Date -Format yyyy-MM-dd).log"

# Tìm claude: PATH, rồi bản đi kèm app Claude desktop (bản mới nhất)
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    $claude = Get-ChildItem "$env:LOCALAPPDATA\Claude-Data\*\claude-code\*\*\claude.exe" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $claude) { throw "Không tìm thấy lệnh claude" }

try {
    if ($Mode -eq "weekly") { python scripts\collect_sources.py *>> $log }
    & $claude -p "/$Mode" --permission-mode acceptEdits `
        --allowedTools "Read" "Write" "Edit" "Glob" "Grep" "WebSearch" "Task" *>> $log
    # đồng bộ lên Supabase để nhân viên thấy ngay (lỗi đồng bộ không làm hỏng cả quy trình)
    try { python scripts\sync_supabase.py both *>> $log } catch { }
    if ($Mode -eq "daily") { python scripts\telegram_bot.py send *>> $log }
    else { python scripts\telegram_bot.py notify "Đã chạy xong /$Mode. Xem reports/ và dashboard." *>> $log }
}
catch {
    python scripts\telegram_bot.py notify "Lỗi khi chạy /$Mode : $($_.Exception.Message)"
    throw
}
