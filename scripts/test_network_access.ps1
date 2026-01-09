# 网络访问测试脚本
# 用于诊断局域网访问问题

param(
    [string]$IP = "192.168.212.120",
    [int]$Port = 5000
)

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "🔍 网络访问诊断工具" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查端口监听状态
Write-Host "1️⃣ 检查端口监听状态..." -ForegroundColor Yellow
$listening = netstat -ano | Select-String ":$Port.*LISTENING"
if ($listening) {
    Write-Host "   ✅ 端口 $Port 正在监听" -ForegroundColor Green
    $listening | ForEach-Object {
        Write-Host "      $_" -ForegroundColor Gray
    }
} else {
    Write-Host "   ❌ 端口 $Port 未在监听" -ForegroundColor Red
}
Write-Host ""

# 2. 检查防火墙规则
Write-Host "2️⃣ 检查防火墙规则..." -ForegroundColor Yellow
$firewallRules = Get-NetFirewallRule | Where-Object { 
    $_.DisplayName -like "*$Port*" -or 
    $_.DisplayName -like "*Douyin*" -or
    ($_.LocalPort -eq $Port -and $_.Direction -eq "Inbound")
} | Select-Object DisplayName, Enabled, Direction, Action

if ($firewallRules) {
    Write-Host "   ✅ 找到防火墙规则:" -ForegroundColor Green
    $firewallRules | ForEach-Object {
        $status = if ($_.Enabled) { "✅ 已启用" } else { "❌ 已禁用" }
        Write-Host "      $($_.DisplayName) - $status - $($_.Direction) - $($_.Action)" -ForegroundColor Gray
    }
} else {
    Write-Host "   ⚠️  未找到相关防火墙规则" -ForegroundColor Yellow
    Write-Host "   建议运行: .\scripts\open_firewall_port.ps1 $Port" -ForegroundColor Gray
}
Write-Host ""

# 3. 测试本地连接
Write-Host "3️⃣ 测试本地连接 (localhost:$Port)..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:$Port" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "   ✅ 本地连接成功 (状态码: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "   ❌ 本地连接失败: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# 4. 测试局域网连接
Write-Host "4️⃣ 测试局域网连接 ($IP`:$Port)..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://$IP`:$Port" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "   ✅ 局域网连接成功 (状态码: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "   ❌ 局域网连接失败: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   错误详情: $($_.Exception)" -ForegroundColor Gray
}
Write-Host ""

# 5. 测试端口连通性
Write-Host "5️⃣ 测试端口连通性 ($IP`:$Port)..." -ForegroundColor Yellow
$test = Test-NetConnection -ComputerName $IP -Port $Port -WarningAction SilentlyContinue
if ($test.TcpTestSucceeded) {
    Write-Host "   ✅ 端口 $Port 可达" -ForegroundColor Green
} else {
    Write-Host "   ❌ 端口 $Port 不可达" -ForegroundColor Red
    Write-Host "   可能原因:" -ForegroundColor Yellow
    Write-Host "      - 防火墙阻止了连接" -ForegroundColor Gray
    Write-Host "      - Flask 应用未监听 0.0.0.0" -ForegroundColor Gray
    Write-Host "      - 网络配置问题" -ForegroundColor Gray
}
Write-Host ""

# 6. 获取本机 IP 地址
Write-Host "6️⃣ 本机网络信息..." -ForegroundColor Yellow
$localIPs = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -notlike "127.*" -and 
    $_.InterfaceAlias -notlike "*Loopback*" 
} | Select-Object IPAddress, InterfaceAlias

if ($localIPs) {
    Write-Host "   本机 IP 地址:" -ForegroundColor Gray
    $localIPs | ForEach-Object {
        $marker = if ($_.IPAddress -eq $IP) { " ← 当前测试 IP" } else { "" }
        Write-Host "      $($_.IPAddress) ($($_.InterfaceAlias))$marker" -ForegroundColor Gray
    }
} else {
    Write-Host "   ⚠️  未找到本机 IP 地址" -ForegroundColor Yellow
}
Write-Host ""

# 7. 检查 Flask 应用配置
Write-Host "7️⃣ 检查 Flask 配置..." -ForegroundColor Yellow
$flaskHost = $env:FLASK_HOST
$flaskPort = $env:FLASK_PORT
Write-Host "   FLASK_HOST: $(if ($flaskHost) { $flaskHost } else { '未设置 (默认: 0.0.0.0)' })" -ForegroundColor Gray
Write-Host "   FLASK_PORT: $(if ($flaskPort) { $flaskPort } else { '未设置 (默认: 5000)' })" -ForegroundColor Gray
Write-Host ""

# 总结和建议
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "📋 诊断总结" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 如果局域网无法访问，请尝试以下步骤:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. 确保 Flask 监听 0.0.0.0 (不是 127.0.0.1)" -ForegroundColor White
Write-Host "   检查方法: netstat -ano | findstr :5000" -ForegroundColor Gray
Write-Host "   应该显示: 0.0.0.0:5000" -ForegroundColor Gray
Write-Host ""
Write-Host "2. 开放防火墙端口" -ForegroundColor White
Write-Host "   运行: .\scripts\open_firewall_port.ps1 $Port" -ForegroundColor Gray
Write-Host ""
Write-Host "3. 检查是否有其他服务占用端口" -ForegroundColor White
Write-Host "   运行: netstat -ano | findstr :$Port" -ForegroundColor Gray
Write-Host ""
Write-Host "4. 重启 Flask 应用" -ForegroundColor White
Write-Host "   确保使用: .\run_web.ps1 或 uv run python run_web.py" -ForegroundColor Gray
Write-Host ""
Write-Host "5. 清除浏览器缓存并重试" -ForegroundColor White
Write-Host ""
