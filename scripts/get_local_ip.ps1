# 获取本机局域网 IP 地址脚本
# 用于查找正确的局域网访问地址

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "🔍 查找本机局域网 IP 地址" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 获取所有 IPv4 地址
$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -notlike "127.*" -and 
    $_.IPAddress -notlike "169.254.*" -and
    $_.IPAddress -notlike "198.18.*" -and
    $_.InterfaceAlias -notlike "*Loopback*" -and
    $_.InterfaceAlias -notlike "*WSL*" -and
    $_.InterfaceAlias -notlike "*Hyper-V*"
} | Select-Object IPAddress, InterfaceAlias, PrefixOrigin

if ($ips) {
    Write-Host "✅ 找到以下局域网 IP 地址:" -ForegroundColor Green
    Write-Host ""
    
    $ips | ForEach-Object {
        $marker = if ($_.PrefixOrigin -eq "Dhcp") { " (推荐 - DHCP)" } else { "" }
        Write-Host "   📍 $($_.IPAddress) - $($_.InterfaceAlias)$marker" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "💡 建议使用 DHCP 分配的 IP 地址进行局域网访问" -ForegroundColor Yellow
    Write-Host ""
    
    # 推荐 IP（DHCP 分配的）
    $recommended = $ips | Where-Object { $_.PrefixOrigin -eq "Dhcp" } | Select-Object -First 1
    if ($recommended) {
        Write-Host "🎯 推荐访问地址: http://$($recommended.IPAddress):5000" -ForegroundColor Green
    } else {
        $first = $ips | Select-Object -First 1
        Write-Host "🎯 建议访问地址: http://$($first.IPAddress):5000" -ForegroundColor Green
    }
} else {
    Write-Host "⚠️  未找到合适的局域网 IP 地址" -ForegroundColor Yellow
    Write-Host "   请检查网络连接" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
