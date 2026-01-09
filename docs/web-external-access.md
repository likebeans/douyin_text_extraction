# Web 界面外网访问配置指南

本文档说明如何配置 Flask Web 应用，使其可以从外网访问。

## 🚀 快速开始

### 1. 启动服务（默认已配置外网访问）

```bash
# 方式一：使用 PowerShell 脚本
.\run_web.ps1

# 方式二：使用 Python 脚本
uv run python run_web.py

# 方式三：指定端口
.\run_web.ps1 8080
```

启动后，你会看到类似以下的输出：

```
======================================================================
🎬 抖音视频文本提取工具 - Web 界面
======================================================================

📱 本地访问: http://localhost:5000
🌐 局域网访问: http://192.168.1.100:5000

🌍 外网访问配置:
   1. 确保 Windows 防火墙已开放端口 5000
   2. 如果使用路由器，需要配置端口转发（端口: 5000）
   3. 外网访问地址: http://<你的公网IP>:5000

💡 提示: 按 Ctrl+C 停止服务
======================================================================
```

## 📋 配置步骤

### 步骤 1: 开放 Windows 防火墙端口

#### 方法一：使用 PowerShell（推荐）

```powershell
# 以管理员身份运行 PowerShell，执行以下命令
New-NetFirewallRule -DisplayName "Douyin Text Extractor Web" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

#### 方法二：使用图形界面

1. 打开"Windows 安全中心" → "防火墙和网络保护"
2. 点击"高级设置"
3. 在"入站规则"中，点击"新建规则"
4. 选择"端口" → 下一步
5. 选择"TCP"，输入端口号（如 5000）→ 下一步
6. 选择"允许连接" → 下一步
7. 应用所有配置文件 → 下一步
8. 输入规则名称（如 "Douyin Web"）→ 完成

### 步骤 2: 配置路由器端口转发（如果需要从外网访问）

如果你需要从互联网访问你的服务（而不仅仅是局域网），需要配置路由器端口转发：

1. **查找你的公网 IP**
   ```bash
   # 在浏览器访问
   https://www.ipip.net/
   # 或
   https://ip.sb/
   ```

2. **登录路由器管理界面**
   - 通常地址：`http://192.168.1.1` 或 `http://192.168.0.1`
   - 默认用户名/密码通常在路由器背面

3. **配置端口转发**
   - 找到"端口转发"或"虚拟服务器"功能
   - 添加新规则：
     - **外部端口**: 5000（或你选择的端口）
     - **内部 IP**: 你的电脑局域网 IP（如 192.168.1.100）
     - **内部端口**: 5000
     - **协议**: TCP
   - 保存配置

4. **测试外网访问**
   ```
   http://<你的公网IP>:5000
   ```

### 步骤 3: 环境变量配置（可选）

你可以通过环境变量自定义配置：

```bash
# Windows PowerShell
$env:FLASK_HOST = "0.0.0.0"      # 监听所有网络接口
$env:FLASK_PORT = "5000"          # 端口号
$env:FLASK_DEBUG = "False"        # 生产环境建议关闭调试模式

# 然后启动服务
uv run python run_web.py
```

或在 `.env` 文件中配置：

```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
```

## 🔒 安全建议

### 生产环境配置

1. **关闭调试模式**
   ```bash
   $env:FLASK_DEBUG = "False"
   ```

2. **使用反向代理（推荐）**
   - 使用 Nginx 或 Apache 作为反向代理
   - 配置 HTTPS（使用 Let's Encrypt 免费证书）
   - 添加访问认证（可选）

3. **限制访问 IP（可选）**
   - 在 Flask 应用中添加 IP 白名单
   - 或在防火墙中配置 IP 限制

4. **使用环境变量保护敏感信息**
   - 不要在代码中硬编码 API Key
   - 使用 `.env` 文件或环境变量

### Nginx 反向代理配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 使用 Gunicorn 部署（生产环境推荐）

```bash
# 安装 Gunicorn
uv add gunicorn

# 启动服务（生产模式）
gunicorn -w 4 -b 0.0.0.0:5000 web_app:app
```

## 🌐 访问地址说明

### 本地访问
- 地址：`http://localhost:5000`
- 说明：只能在本机访问

### 局域网访问
- 地址：`http://<局域网IP>:5000`
- 说明：同一局域网内的其他设备可以访问
- 获取局域网 IP：
  ```bash
  # Windows
  ipconfig
  # Linux/Mac
  ifconfig
  ```

### 外网访问
- 地址：`http://<公网IP>:5000` 或 `http://<域名>:5000`
- 说明：需要配置端口转发或使用反向代理
- 获取公网 IP：访问 https://ip.sb/

## ❓ 常见问题

### Q1: 无法从外网访问

**可能原因：**
1. 防火墙未开放端口
2. 路由器未配置端口转发
3. 你的网络使用的是运营商 NAT（无法直接访问）

**解决方法：**
1. 检查防火墙设置
2. 检查路由器端口转发配置
3. 考虑使用内网穿透工具（如 frp、ngrok）

### Q2: 局域网内其他设备无法访问

**可能原因：**
1. Flask 未监听 `0.0.0.0`（只监听了 `127.0.0.1`）
2. Windows 防火墙阻止了连接

**解决方法：**
1. 确保 `FLASK_HOST=0.0.0.0`
2. 在防火墙中添加端口规则

### Q3: 如何获取本机 IP 地址？

```bash
# Windows PowerShell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" }

# Windows CMD
ipconfig

# Linux/Mac
ifconfig | grep "inet "
```

### Q4: 可以使用其他端口吗？

可以，通过环境变量或命令行参数：

```bash
# PowerShell
$env:FLASK_PORT = "8080"
.\run_web.ps1 8080

# Python
$env:FLASK_PORT = "8080"
uv run python run_web.py
```

### Q5: 生产环境建议

1. **使用 Gunicorn 或 uWSGI**
   - 更好的性能和稳定性
   - 支持多进程

2. **配置 HTTPS**
   - 使用 Nginx 反向代理 + Let's Encrypt

3. **添加访问日志**
   - 监控访问情况

4. **配置监控和告警**
   - 服务可用性监控

## 📝 示例配置

### 开发环境（局域网访问）

```bash
# .env 文件
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True
```

### 生产环境（外网访问）

```bash
# .env 文件
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False

# 使用 Gunicorn 启动
gunicorn -w 4 -b 0.0.0.0:5000 --access-logfile - --error-logfile - web_app:app
```

## 🔗 相关文档

- [Flask 官方文档 - 部署](https://flask.palletsprojects.com/en/latest/deploying/)
- [Nginx 反向代理配置](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [Gunicorn 文档](https://docs.gunicorn.org/)

---

**最后更新**: 2026-01-09  
**版本**: 1.0
