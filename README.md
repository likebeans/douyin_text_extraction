# 抖音视频文本提取工具

一个通过命令行或本地 Web 界面提取抖音视频语音文本的 Python 工具。默认使用阿里云 DashScope；也可安装可选的本地 Whisper 依赖。项目版本为 `0.3.0`，当前接口和平台页面变化可能影响解析与转写。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 功能

- 从抖音短链接、视频链接或分享文本解析视频。
- 通过 DashScope 或本地 Whisper 进行语音识别。
- CLI 支持 Markdown、纯文本和 JSON 输出，可选择输出路径。
- Web 页面支持提交提取任务；本机模式可以通过配置页面编辑 `.env`。
- DashScope 转写失败时，可按需配置 OSS 与 FFmpeg 作为备用流程。

## 快速开始

需要 Python 3.10 或更高版本以及 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/likebeans/douyin_text_extraction.git
cd douyin_text_extraction
uv sync --locked
cp .env.example .env
```

编辑 `.env`，将 `DASHSCOPE_API_KEY` 设置为自己的 DashScope API Key。Windows PowerShell 可用 `Copy-Item .env.example .env` 复制模板。

```bash
uv run douyin-extract extract "https://v.douyin.com/你的短链接/"
```

默认结果保存在 `output/`。项目不包含真实凭据；`.env` 已加入 Git 忽略规则。

## CLI 用法

```bash
# Markdown（默认），保存到 output/douyin_<视频ID>.md
uv run douyin-extract extract "抖音链接或分享文本"

# 纯文本与 JSON
uv run douyin-extract extract "抖音链接" --format txt
uv run douyin-extract extract "抖音链接" --format json

# 指定文件名或路径；扩展名会按 --format 确定
uv run douyin-extract extract "抖音链接" --format json --output reports/result.json

# 仅输出到终端，不写文件
uv run douyin-extract extract "抖音链接" --format json --no-save > result.json

# 离线查看当前配置和本地依赖；不会验证远端凭据或提交转写任务
uv run douyin-extract config-check
uv run douyin-extract version
```

JSON 模式下，标准输出只包含 JSON，诊断信息写到标准错误。输出路径会尊重 `--output`；只给文件名时写入 `OUTPUT_DIR`，给相对目录或绝对路径时使用指定目录。

### 本地 Whisper

本地模式默认不安装，以避免下载较大的机器学习依赖。安装后设置 `ASR_PROVIDER=local`，可选设置 `WHISPER_MODEL`：

```bash
uv sync --extra local
```

本地识别还需要系统 FFmpeg。首次加载模型时，Whisper 可能需要下载模型文件。`REQUEST_TIMEOUT` 控制 HTTP 连接和单次读取等待时间；`DOWNLOAD_TIMEOUT` 默认给整个媒体下载 300 秒，`FFMPEG_TIMEOUT` 单独限制 FFmpeg 音频提取进程。

分享页有时会返回 HTTP 200，但暂时缺少视频详情。工具会复用会话并按 `RETRY_TIMES` 做有限重试；持续缺数据、明确拒绝访问或非视频内容仍会返回错误，不保证所有链接均可提取。

## Web 界面

本机开发启动：

```bash
uv run douyin-web
```

默认监听 `127.0.0.1:5000`，浏览器打开 <http://127.0.0.1:5000>。本机运行时，`/config` 页面可将设置保存到工作目录的 `.env`。环境变量优先于 `.env`；由环境变量提供的值不能通过页面更改。保存 `.env` 不会修改当前进程环境，重新读取的设置会在后续请求生效。

`POST /api/extract` 会在 HTTP 请求期间同步完成转写，不提供任务 ID、队列查询或进度推送；超过并发上限时返回 `429`，客户端应设置足够长的读取超时。

要允许其他设备连接，先设置随机 `WEB_API_TOKEN`，再设置 `FLASK_HOST=0.0.0.0`，并保持 `FLASK_DEBUG=false`。浏览器页面会要求输入令牌，令牌只保留在当前页面内存；API 客户端可使用 `Authorization: Bearer <token>` 或 `X-API-Token: <token>`。不要把未加密的服务直接暴露到互联网，远程访问应放在启用 HTTPS 的反向代理之后。若浏览器 Origin 与应用请求 Origin 不同，可设置 `WEB_PUBLIC_ORIGIN=https://your-host.example` 精确允许指定的外部 Origin；仅在 `WEB_API_TOKEN` 已设置时生效，值不含路径、查询或片段。应用不信任客户端任意提供的 forwarded headers。详见 [Web 外部访问说明](docs/web-external-access.md) 和 [API 文档](docs/API对接文档.md)。

## Docker Compose

在项目目录创建 `.env` 并填写 DashScope Key 与非空的 `WEB_API_TOKEN`。可生成令牌：

```bash
openssl rand -hex 32
```

然后启动：

```bash
docker compose up -d --build
docker compose logs -f douyin-api
docker compose down
```

Compose 将宿主机端口绑定到 `127.0.0.1`，容器内监听 `0.0.0.0:5000`，关闭调试模式，并禁用 Web 配置写入。浏览器打开 Web 页面后输入 `WEB_API_TOKEN` 即可提取；`/api/config` 在此模式下禁用。若需其他设备访问，应由 HTTPS 反向代理转发到本机端口。

镜像默认不包含 Whisper。如需在镜像中安装本地 ASR 依赖：

```bash
INSTALL_LOCAL_ASR=true docker compose up -d --build
```

Compose 挂载 `./output` 和 `./temp` 作为数据目录。`.env` 不会复制进镜像；Compose 通过容器环境变量注入配置。

## 配置

常用设置与默认值见 [.env.example](.env.example)。完整说明见 [环境变量配置指南](docs/ENV_CONFIG_GUIDE.md) 和 [OSS 配置指南](docs/OSS_GUIDE.md)。`WEB_API_TOKEN` 为空时，Web API 只接受来自本机回环地址的请求；非本机监听必须设置令牌。设置令牌后，提取和配置 API 均需要令牌，健康检查 `/api/health` 例外。媒体 URL 和每一跳重定向只允许 `src/media_url.py` 列出的平台/CDN 域名；这是域名校验，不提供 DNS/IP 隔离。

OSS 兜底默认使用 3600 秒有效的签名 URL，Bucket 可保持私有。`OSS_ENDPOINT_INTERNAL` 仅用于上传与删除，签名 URL 由 `OSS_ENDPOINT` 公网地址生成。若配置 `OSS_CDN_DOMAIN`，CDN 不附带 OSS 签名，需要部署者自行配置回源权限。

## 开发与测试

```bash
uv sync --locked --all-groups
uv run pytest
uv build --wheel
```

普通测试在临时工作目录运行并拦截网络连接，不读取项目的真实 `.env`。真实 OSS 测试默认不会运行；如需主动执行，请先确认使用的是专用测试 Bucket 和可删除的对象，再运行：

```bash
uv run pytest --run-integration -m integration tests/test_oss_client.py
```

更多说明见 [贡献指南](CONTRIBUTING.md)。

## 文档

- [OSS 兜底配置](docs/OSS_GUIDE.md)
- [文档索引](docs/README.md)
- [环境变量配置](docs/ENV_CONFIG_GUIDE.md)
- [DashScope 与本地 Whisper](docs/ASR_PROVIDER_GUIDE.md)
- [Web API 对接](docs/API对接文档.md)
- [Web 外部访问](docs/web-external-access.md)
- [安全策略](SECURITY.md)
- [变更记录](CHANGELOG.md)

## License

[MIT](LICENSE)
