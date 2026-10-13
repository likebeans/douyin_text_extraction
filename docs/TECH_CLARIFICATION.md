# 技术说明

本文概述当前项目的处理路径。DashScope、抖音页面与 OSS 的行为由对应服务提供方控制，并可能发生变化；请以其最新官方文档和实际配置为准。

## DashScope 识别流程

云端流程将获取到的视频媒体 URL 提交给 DashScope 文件识别接口，等待任务状态，再读取转写结果。请求等待时限通过 `ASR_TIMEOUT` 配置。转写结果和处理时间受媒体内容及上游服务影响。本项目没有发布准确率、时延、并发配额或固定价格的独立基准。

## 本地处理流程

本地 Whisper 模式先将视频下载至临时目录，再使用 FFmpeg 提取音轨并调用 Whisper。该可选依赖需通过 `uv sync --extra local` 安装。平台页面解析仍需网络连接；本地语音识别不会因此变成完全离线流程。

## OSS 备用流程

DashScope 直接 URL 转写失败时，如果配置并启用了 OSS 备用流程，应用可下载视频、提取音频、上传至用户配置的 Bucket，再向 DashScope 提交音频 URL。默认签名 URL 有效期、Endpoint 和 CDN 行为请查看[当前 OSS 配置指南](OSS_GUIDE.md)。

## 相关资源

- [DashScope 官方文档](https://help.aliyun.com/zh/model-studio/)
- [环境变量配置](ENV_CONFIG_GUIDE.md)
- [ASR 提供商指南](ASR_PROVIDER_GUIDE.md)
