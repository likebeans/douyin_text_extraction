# 语音识别方式

项目支持 DashScope 云端识别与本地 Whisper。两种方式使用同一提取流程；服务可用性、耗时、识别结果和费用取决于媒体内容、硬件、网络及第三方服务，本项目不提供未经测量的准确率或时延承诺。

## DashScope

默认模式。设置 `DASHSCOPE_API_KEY`，可通过 `ASR_MODEL` 选择模型。处理时媒体 URL 会交给 DashScope；若启用 OSS 备用流程，处理失败后还可能下载视频、提取音频并上传至你配置的 OSS Bucket。请查看第三方服务的数据处理与计费条款。

```dotenv
ASR_PROVIDER=dashscope
DASHSCOPE_API_KEY=replace-with-your-dashscope-api-key
ASR_MODEL=paraformer-v2
```

## 本地 Whisper

Whisper 不属于默认依赖。按需安装并设置模型：

```bash
uv sync --extra local
```

```dotenv
ASR_PROVIDER=local
WHISPER_MODEL=base
```

本地流程需要 FFmpeg，并需下载视频到本机再提取音轨。Whisper 首次使用时可能下载模型文件；模型大小、内存占用及处理速度因模型和硬件而异。虽然语音识别在本机执行，解析抖音链接仍需要访问抖音页面。

## 临时切换

CLI 支持单次调用覆盖提供商：

```bash
uv run douyin-extract extract "抖音链接" --asr-provider local
uv run douyin-extract extract "抖音链接" --asr-provider dashscope
```

配置检查不会访问第三方服务，也不会验证凭据是否有效。更多变量见 [环境变量配置指南](ENV_CONFIG_GUIDE.md)。
