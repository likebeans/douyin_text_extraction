# Web 服务远程访问

Web 服务默认只监听 `127.0.0.1:5000`。先在本机确认可用，再决定是否需要让其他设备访问。

## 本地运行

```bash
uv run douyin-web
```

浏览器访问 <http://127.0.0.1:5000>。若配置了 `WEB_API_TOKEN`，页面会提示输入令牌；令牌只保存在当前页面内存。`/config` 可用于管理本地 `.env`，但环境变量覆盖项不可编辑。

## 允许局域网或代理连接

先在 `.env` 设置随机令牌并关闭调试：

```dotenv
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
WEB_API_TOKEN=替换为随机生成的长令牌
WEB_PUBLIC_ORIGIN=https://your-host.example
```

`WEB_PUBLIC_ORIGIN` 用于浏览器经 HTTPS 反向代理访问时允许指定的外部 Origin。仅在设置了 `WEB_API_TOKEN` 时生效，必须是精确的 Origin 值，不含路径、查询或片段；应用不信任客户端任意提供的 forwarded headers。若只通过代理访问，也可按需填写此项。

生成随机令牌的示例：

```bash
openssl rand -hex 32
```

应用在非回环监听且没有令牌时拒绝启动。API 客户端使用 `Authorization: Bearer <令牌>` 或 `X-API-Token: <令牌>` 请求头。令牌不要放在 URL、客户端脚本文件或日志中。

## Docker Compose

Compose 默认使用 Waitress，关闭调试模式和 Web 配置写入，并将宿主机端口绑定到 `127.0.0.1`。`.env` 必须包含非空 `WEB_API_TOKEN`。本机浏览器打开服务地址后输入令牌即可调用提取 API；`/api/config` 返回 404，因为 Compose 的环境变量注入不会写回持久化 `.env`。

远程访问应通过配置了 HTTPS 的反向代理转发至本机绑定端口，并限制代理入口和网络访问。不要直接把开发服务器或未加密端口映射到公网。令牌提供 API 访问控制，但不替代 TLS、网络隔离或用户级授权。
