# Web API 对接文档

本文档描述当前 Web 服务提供的接口。默认服务地址为 `http://127.0.0.1:5000`；跨主机访问请使用 HTTPS 反向代理。

## 认证

设置 `WEB_API_TOKEN` 后，除 `GET /api/health` 外，所有 `/api/*` 请求都必须带令牌。支持以下任一种请求头：

```http
Authorization: Bearer <WEB_API_TOKEN>
```

或：

```http
X-API-Token: <WEB_API_TOKEN>
```

浏览器界面会提示输入令牌，并仅在当前页面内存中使用。令牌未设置时，API 仅接受来自本机回环地址的请求。浏览器跨站请求会被拒绝。

## 接口

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| `GET` | `/api/health` | 健康检查，返回 `{"ok": true}` | 不需要 |
| `POST` | `/api/extract` | 同步解析与转写一个视频 | 需要令牌；无令牌时仅限本机 |
| `GET` | `/api/config` | 读取非敏感配置及密钥是否已配置 | 同上；`WEB_CONFIG_ENABLED=false` 时返回 404 |
| `POST` | `/api/config` | 更新允许通过本机配置页面修改的 `.env` 项 | 同上；`WEB_CONFIG_ENABLED=false` 时返回 404 |
| `GET` | `/` | Web 提取页面 | 页面本身无需 API 令牌 |
| `GET` | `/config` | Web 配置页面 | 页面本身无需 API 令牌；读写接口仍需认证且可被禁用 |

### 提取视频文本

请求体必须是 JSON 对象，`link` 为必填字符串，长度最多 8192 个字符。

```bash
curl --fail-with-body \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${WEB_API_TOKEN}" \
  -d '{"link":"https://v.douyin.com/你的短链接/"}' \
  http://127.0.0.1:5000/api/extract
```

成功时返回 `success`、`metadata` 和 `text`。`metadata` 包含 `video_id`、`title`、`author`、`duration`、`video_url`、`cover_url` 和 `douyin_url`；其中媒体 URL 来自抖音页面，可能随平台变化。下载媒体时，初始 URL 和每一跳重定向都必须属于 `src/media_url.py` 列出的平台或 CDN 域名。这是域名校验，不是 DNS/IP 隔离。

```json
{
  "success": true,
  "metadata": {
    "video_id": "示例视频ID",
    "title": "视频标题",
    "author": "作者昵称",
    "duration": 214,
    "video_url": "https://example.invalid/video.mp4",
    "cover_url": "https://example.invalid/cover.jpg",
    "douyin_url": "https://www.douyin.com/video/示例视频ID"
  },
  "text": "转写得到的文本"
}
```

失败时返回 `success: false` 和 `error`。常见状态码包括 `400`（参数或配置错误）、`401`（令牌缺失或错误）、`403`（非本机请求未配置令牌或跨站请求）、`404`（配置 API 已禁用）、`429`（并发槽位已满，请稍后重试）、`502`（平台或转写上游失败）和 `500`（内部错误）。

提取在 HTTP 请求期间同步执行。服务当前没有任务 ID、排队查询或进度推送；达到并发上限时会直接返回 `429`。客户端应根据视频长度设置足够的请求超时，并在需要时调整 `ASR_TIMEOUT`。连接超时不代表服务端任务一定已经取消。

### 读取与保存配置

配置 API 只适用于启用了 `WEB_CONFIG_ENABLED` 的本机配置界面。GET 响应不会返回密钥原文，只返回空的密钥字段与 `*_CONFIGURED` 布尔状态；若配置由环境变量提供，会列在 `ENVIRONMENT_FIELDS` 中。POST 只接受已支持的配置字段，环境变量覆盖项不能通过页面修改。密钥字段提交空值表示保留当前值。

Compose 默认设置 `WEB_CONFIG_ENABLED=false`，并且 `env_file` 注入的设置不会写回 `.env`。容器配置应通过部署环境维护；该运行模式下的配置读写接口返回 `404`。

## 部署说明

Compose 默认只将服务发布到宿主机 `127.0.0.1`，并要求 `.env` 中有非空 `WEB_API_TOKEN`。通过反向代理提供远程访问时，使用 TLS，限制代理来源，并保留 `Authorization` 或 `X-API-Token` 请求头。不要在 URL 参数中传递令牌。若浏览器发送的 Origin 与应用看到的请求 Origin 不同，可设置 `WEB_PUBLIC_ORIGIN=https://your-host.example` 精确允许该外部 Origin；只有设置了 `WEB_API_TOKEN` 时生效，值不含路径、查询或片段。应用不信任客户端任意提供的 forwarded headers。
