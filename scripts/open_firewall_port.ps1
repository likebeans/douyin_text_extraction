# Windows 防火墙端口开放脚本
# 使用方法（需要管理员权限）：.\scripts\open_firewall_port.ps1 [端口号]
# 例如：.\scripts\open_firewall_port.ps1 5000

param(
    [int]$Port = 5000,
    [string]$Name = "Douyin Text Extractor Web"
)

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ 需要管理员权限！" -ForegroundColor Red
    Write-Host "请以管理员身份运行 PowerShell，然后执行此脚本" -ForegroundColor Yellow
    exit 1
}

Write-Host "正在配置防火墙规则..." -ForegroundColor Cyan
Write-Host "端口: $Port" -ForegroundColor Gray
Write-Host "名称: $Name" -ForegroundColor Gray
Write-Host ""

# 检查规则是否已存在
$existingRule = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "⚠️  规则已存在，正在更新..." -ForegroundColor Yellow
    Remove-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
}

try {
    # 创建新的防火墙规则
    New-NetFirewallRule `
        -DisplayName $Name `
        -Direction Inbound `
        -LocalPort $Port `
        -Protocol TCP `
        -Action Allow `
        -Profile Any `
        -Description "允许访问抖音视频文本提取工具的 Web 界面" | Out-Null
    
    Write-Host "✅ 防火墙规则已成功创建！" -ForegroundColor Green
    Write-Host ""
    Write-Host "📱 本地访问: http://localhost:$Port" -ForegroundColor Cyan
    Write-Host "🌐 局域网访问: http://<你的局域网IP>:$Port" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "💡 提示: 如果需要外网访问，还需要配置路由器端口转发" -ForegroundColor Yellow
} catch {
    Write-Host "❌ 创建防火墙规则失败: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
