# 环境变量配置

应用通过环境变量读取配置；未设置环境变量时，`Settings` 从当前工作目录的 `.env` 读取值。环境变量优先。`.env` 只适合本机开发或单机运行，不要提交该文件。

```bash
cp .env.example .env
```

编辑 `.env`，至少为默认的 DashScope 模式设置 `DASHSCOPE_API_KEY`。改用 `ASR_PROVIDER=local` 时不需要 DashScope Key，但需执行 `uv sync --extra local` 并安装 FFmpeg。

## 常用选项

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `ASR_PROVIDER` | `dashscope` | `dashscope` 或 `local` |
| `DASHSCOPE_API_KEY` | 空 | DashScope API Key |
| `ASR_MODEL` | `paraformer-v2` | 云端模型；当前 Web 配置页面支持 `paraformer-v2` |
| `WHISPER_MODEL` | `base` | 本地 Whisper 模型大小 |
| `MAX_VIDEO_DURATION` | `600` | 视频时长上限，秒 |
| `OUTPUT_DIR` | `./output` | CLI 默认输出目录 |
| `REQUEST_TIMEOUT` | `30` | HTTP 连接与单次读取等待超时，秒 |
| `DOWNLOAD_TIMEOUT` | `300` | 单个媒体文件的下载总时限，秒 |
| `RETRY_TIMES` | `3` | HTTP 重试次数；分享页暂缺视频详情时也最多重试此次数 |
| `ASR_TIMEOUT` | `600` | 云端 ASR 等待时限，秒 |
| `FFMPEG_TIMEOUT` | `120` | FFmpeg 本地音频提取进程超时，秒 |
| `MAX_DOWNLOAD_BYTES` | `536870912` | 本地流程下载大小上限，字节 |
| `TEMP_DIR` | `./temp` | 临时文件目录 |
| `CLEANUP_TEMP_FILES` | `true` | 成功或失败后清理本地流程临时文件 |

`REQUEST_TIMEOUT` 限制 HTTP 连接和单次读取等待，`DOWNLOAD_TIMEOUT` 独立限制媒体下载总耗时，`FFMPEG_TIMEOUT` 限制 FFmpeg 进程运行时间。持续传输数据的下载不会仅因超过 30 秒而中断，但仍受下载总时限和大小上限约束。

当分享页成功响应却暂缺 `videoInfoRes` 时，工具复用同一会话并等待后重试，最多共请求 `RETRY_TIMES + 1` 次。明确拒绝、视频 ID 不匹配和格式无效的响应不会走这一重试。

## OSS 备用流程

该流程默认关闭。需要时设置 `OSS_ENABLE_FALLBACK=true`，并填写 `OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`、`OSS_BUCKET_NAME` 和 `OSS_ENDPOINT`。只授予专用 Bucket 所需的最小权限。可选项包括 `OSS_ENDPOINT_INTERNAL`、`OSS_REGION` 和 `OSS_CDN_DOMAIN`。安装 FFmpeg 后，DashScope 直接使用媒体 URL 失败时才会尝试本地处理并上传 OSS。默认通过 OSS 生成 3600 秒有效的签名 URL，Bucket 可保持私有；内部 Endpoint 只用于对象传输。如果配置 CDN，需由部署者设置回源权限且 CDN URL 不带 OSS 签名。详见 [OSS 配置指南](OSS_GUIDE.md)。

## Web 设置

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `FLASK_HOST` | `127.0.0.1` | Web 监听地址；远程监听需要令牌 |
| `FLASK_PORT` | `5000` | 本地 Web 端口 |
| `FLASK_DEBUG` | `false` | 调试模式；只能绑定本机地址 |
| `WEB_API_TOKEN` | 空 | 保护非健康检查的 API；建议生成随机长令牌 |
| `WEB_PUBLIC_ORIGIN` | 空 | HTTPS 反向代理的外部 Origin；仅与令牌配合使用 |
| `WEB_CONFIG_ENABLED` | `true` | 是否启用本机 `/config` 页面对应的配置 API |
| `WEB_MAX_CONCURRENT_EXTRACTIONS` | `2` | 同时处理的提取任务数；超出时 API 返回 `429` |

令牌可用 `openssl rand -hex 32` 生成。远程 API 客户端将令牌放在 `Authorization: Bearer ...` 或 `X-API-Token` 请求头中。不要放入 URL 或日志。

经 HTTPS 反向代理提供浏览器访问时，如外部 Origin 与应用请求 Origin 不同，可设置 `WEB_PUBLIC_ORIGIN=https://your-host.example` 精确允许该 Origin。该选项只在设置了 `WEB_API_TOKEN` 时生效，值须是不含路径、查询或片段的完整 Origin；应用不信任客户端任意提供的 forwarded headers。

本机 Web 配置页面通过 API 保存已允许修改的值到工作目录 `.env`。写入不会改动当前进程环境；后续请求重新加载设置。环境变量提供的值是只读覆盖项。Docker Compose 默认将配置 API 关闭，因为 `env_file` 注入的值不会持久化到容器 `.env`；Compose 部署请从宿主机环境配置服务。

## 检查配置

```bash
uv run douyin-extract config-check
```

该命令只检查本地配置格式、必需项和 FFmpeg 是否可用，不会调用抖音、DashScope 或 OSS，也不验证凭据是否能连接远端服务。
