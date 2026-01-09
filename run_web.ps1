# 抖音视频文本提取工具 - Web 界面启动脚本
# 使用方法: .\run_web.ps1 [端口号]
# 例如: .\run_web.ps1 8080

# 设置编码
$env:PYTHONIOENCODING = 'utf-8'

# 获取端口号参数（如果提供）
$port = if ($args.Count -gt 0) { $args[0] } else { 5000 }

# 设置环境变量
$env:FLASK_HOST = "0.0.0.0"
$env:FLASK_PORT = $port
$env:FLASK_DEBUG = "True"

# 获取本机 IP 地址
function Get-LocalIP {
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.InterfaceAlias -notlike "*Loopback*" } | Select-Object -First 1).IPAddress
        if (-not $ip) {
            $ip = "localhost"
        }
        return $ip
    } catch {
        return "localhost"
    }
}

$localIP = Get-LocalIP

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "🎬 抖音视频文本提取工具 - Web 界面" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否存在 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  未找到 .env 文件，请先配置 API Key" -ForegroundColor Yellow
    Write-Host "   可以通过 Web 界面配置：http://localhost:$port/config" -ForegroundColor Yellow
    Write-Host "   或创建 .env 文件，参考 env.example" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "正在启动 Web 服务..." -ForegroundColor Green
Write-Host ""
Write-Host "📱 本地访问: http://localhost:$port" -ForegroundColor Cyan
Write-Host "🌐 局域网访问: http://$localIP`:$port" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌍 外网访问配置:" -ForegroundColor Yellow
Write-Host "   1. 确保 Windows 防火墙已开放端口 $port" -ForegroundColor Gray
Write-Host "   2. 如果使用路由器，需要配置端口转发（端口: $port）" -ForegroundColor Gray
Write-Host "   3. 外网访问地址: http://<你的公网IP>:$port" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 提示: 按 Ctrl+C 停止服务" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 运行 Web 应用
uv run python run_web.py
