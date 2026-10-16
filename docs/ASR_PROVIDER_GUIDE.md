# 语音识别方式

项目支持 DashScope 云端识别与本地 Whisper / SenseVoiceSmall。两种方式使用同一提取流程；服务可用性、耗时、识别结果和费用取决于媒体内容、硬件、网络及第三方服务，本项目不提供未经测量的准确率或时延承诺。

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

本机 Web 配置页可以选择 `WHISPER_MODEL`，下一次提取生效。`tiny` / `base` 优先节省资源；`small`、`medium`、`large`、`turbo` 提供更多模型选择，效果需结合实际音频判断。`small` 首次下载约 484 MB，`turbo` 约 1.6 GB；CPU 转写可能比视频本身更长。设置了 `WHISPER_MODEL` 环境变量时，页面不能覆盖它。

Whisper 使用 `beam_size=5`，并关闭跨窗口前文条件，减少错误文本持续传播形成的重复循环。保留默认温度回退和静音门限；不会依据重复词直接删除内容，也不把视频标题或预想台词写进提示。GPU 仅按 Whisper 默认使用可用的 CUDA，否则使用 CPU；本轮未默认启用 Apple MPS。

## 本地中文 SenseVoiceSmall

中文口语可尝试 SenseVoiceSmall int8（FunASR / FunAudioLLM），通过 sherpa-onnx 在 CPU 上运行并生成标点。不需要 DashScope Key，也不会将音频上传至识别服务。

```bash
uv sync --extra local-chinese
# 同时保留 Whisper：uv sync --extra local --extra local-chinese
```

```dotenv
ASR_PROVIDER=local
LOCAL_ASR_ENGINE=sensevoice
```

也可以在 Web 配置页选择“本地识别 → SenseVoiceSmall”。首次使用从 [sherpa-onnx 官方发布页](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2)下载约 163 MB 压缩包，校验 SHA256 后仅安装模型和词表，解压后约 240 MB。缓存位于 `${XDG_CACHE_HOME:-~/.cache}/douyin-text-extractor/`，后续加载会校验文件。模型不随项目代码分发。

输入使用 FFmpeg 提取的 16 kHz 单声道 PCM WAV。长音频按 12–20 秒附近的低能量位置切段，保证每段不超过 20 秒，并完整保留样本；这不是声学 VAD，不会按音量阈值删除安静说话。只跳过全零静音、移除已知模型控制标签，不做重复词删除或基于标题的内容补写。切段处、方言、重叠说话和商品型号仍可能识别错误，需要核对原视频；不能保证无错字。

### 模型来源与许可

项目代码仍使用 MIT。SenseVoiceSmall 权重由 **FunASR / FunAudioLLM** 提供，适用独立的 [FunASR 模型开源协议 v1.1](https://github.com/modelscope/FunASR/blob/58830eca4012644aac0c3218c3ccc7d98f003fda/MODEL_LICENSE)，不适用本项目 MIT 许可；请保留来源、作者及模型名称。参见 [官方模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall) 与 [sherpa-onnx 转换模型说明](https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html)。协议含独立使用条件，商业使用解释仍待许可方确认，详见 [官方讨论 #334](https://github.com/QwenAudio/SenseVoice/issues/334)，本项目不作无限制商用保证。

## 临时切换

CLI 支持单次调用覆盖提供商：

```bash
uv run douyin-extract extract "抖音链接" --asr-provider local
uv run douyin-extract extract "抖音链接" --asr-provider dashscope
```

配置检查不会访问第三方服务，也不会验证凭据是否有效。更多变量见 [环境变量配置指南](ENV_CONFIG_GUIDE.md)。
