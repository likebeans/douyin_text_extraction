# OSS 兜底配置

DashScope 直接使用抖音视频 URL 转写失败时，可选启用 OSS + FFmpeg 兜底。应用下载视频、提取音频、上传到 OSS，再把音频 URL 交给 DashScope。

## Bucket 与 URL 权限

默认情况下，应用上传对象后使用 OSS SDK 生成带过期时间的 HTTPS GET 签名 URL（默认有效期 3600 秒），供 DashScope 在转写期间读取。Bucket 可以保持私有，不需要开放公共读 ACL。请给应用使用的 RAM 身份授予目标 Bucket 所需的最小权限（上传、删除和签名所需权限）；不要为了方便将 Bucket 设为公共读。

DashScope 必须能在 URL 过期前获取该对象。`OSSClient` 默认签名有效期为 3600 秒；直接使用该客户端的集成可通过 `sign_url_expires` 参数覆盖。应用当前的兜底流程使用默认值。如果使用 DashScope 托管任务，请确认该有效期足以让服务端获取文件。

如果设置 `OSS_ENDPOINT_INTERNAL`，它用于 OSS 对象上传和删除。应用仍使用 `OSS_ENDPOINT` 对应的公网 Endpoint 生成 DashScope 可访问的签名 URL。内网 Endpoint 只应在运行环境能够访问该 Endpoint 时设置。

设置 `OSS_CDN_DOMAIN` 时，返回 URL 指向配置的 HTTPS CDN 域名，不附带 OSS 签名参数。部署者需要单独配置 CDN 到 OSS 的回源访问权限及缓存策略，并确认对象路径可供 DashScope 获取。使用 CDN 时，Bucket 是否需要公共访问取决于 CDN 回源方案；优先使用 CDN 到私有 Bucket 的受控回源授权。

## 配置

在 `.env` 中填写：

```dotenv
DASHSCOPE_API_KEY=replace-with-your-dashscope-api-key
OSS_ENABLE_FALLBACK=true
OSS_ACCESS_KEY_ID=replace-with-your-oss-access-key-id
OSS_ACCESS_KEY_SECRET=replace-with-your-oss-access-key-secret
OSS_BUCKET_NAME=your-bucket-name
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_ENDPOINT_INTERNAL=
OSS_REGION=
OSS_CDN_DOMAIN=
```

应用自动生成带 UUID 的对象名，降低并发任务之间发生路径冲突的机会。成功时会尝试清理上传的临时对象和本地临时文件。

安装并检查 FFmpeg：

```bash
# macOS
brew install ffmpeg

# Debian/Ubuntu
sudo apt-get install ffmpeg

uv run douyin-extract config-check
```

Docker 镜像默认包含 FFmpeg。使用 `docker compose up -d --build` 构建默认镜像；需要本地 Whisper 时，在 Compose 构建前将 `INSTALL_LOCAL_ASR=true` 加入 `.env` 并构建镜像。Whisper 依赖及模型文件体积较大。

## 费用与凭据

DashScope、OSS 存储、请求流量和 CDN 费用依所选地区、用量及账户方案而异，请以云服务控制台显示为准。为此工具创建专用 RAM 身份，限制到单个 Bucket 和必要操作；凭据保存在未跟踪的 `.env` 或部署密钥管理器中，不要提交到仓库。

更多选项见 [环境变量配置指南](ENV_CONFIG_GUIDE.md)。
