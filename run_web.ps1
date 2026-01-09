# 抖音视频文本提取工具 - Web 界面启动脚本
# 使用方法: .\run_web.ps1

# 设置编码
$env:PYTHONIOENCODING = 'utf-8'

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🎬 抖音视频文本提取工具 - Web 界面" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否存在 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  未找到 .env 文件，请先配置 API Key" -ForegroundColor Yellow
    Write-Host "   可以通过 Web 界面配置：http://localhost:5000/config" -ForegroundColor Yellow
    Write-Host "   或创建 .env 文件，参考 env.example" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "正在启动 Web 服务..." -ForegroundColor Green
Write-Host "访问地址: http://localhost:5000" -ForegroundColor Green
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 运行 Web 应用
uv run python run_web.py
