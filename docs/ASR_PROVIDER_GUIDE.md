# ASR 提供商选择指南

## 📋 概述

项目现在支持两种 ASR（语音识别）方式：
- **DashScope（云端）**：使用阿里云 DashScope API，快速准确，需要 API Key
- **Local（本地）**：使用 Whisper 本地模型，完全免费，需要本地资源

---

## 🚀 快速开始

### 方式 1：通过环境变量配置（推荐）

在 `.env` 文件中设置：

```ini
# 使用 DashScope（云端）
ASR_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-your-api-key-here

# 或使用本地 Whisper
ASR_PROVIDER=local
```

### 方式 2：通过命令行参数（临时覆盖）

```bash
# 使用 DashScope（即使配置文件中是 local）
.\run.ps1 extract "链接" --asr-provider dashscope

# 使用本地 Whisper（即使配置文件中是 dashscope）
.\run.ps1 extract "链接" --asr-provider local
```

---

## 📊 两种方式对比

| 特性 | DashScope（云端） | Local（本地） |
|------|------------------|--------------|
| **速度** | ⚡ 快（~20秒/分钟） | 🐌 慢（~2-5分钟/分钟，取决于硬件） |
| **准确率** | ⭐⭐⭐⭐⭐ 98%+ | ⭐⭐⭐⭐ 95%+ |
| **成本** | 💰 ¥0.013/分钟 | ✅ 免费 |
| **隐私** | ⚠️ 数据上传云端 | ✅ 完全本地处理 |
| **依赖** | API Key | Whisper 库 + 模型文件 |
| **网络** | ✅ 需要 | ❌ 不需要 |
| **硬件要求** | 无 | CPU/GPU（推荐 GPU） |

---

## 🔧 详细配置

### DashScope（云端）配置

**优点**：
- ✅ 速度快，准确率高
- ✅ 支持直接传视频 URL，无需下载
- ✅ 自动提取音频
- ✅ 支持多种模型（Paraformer、Fun-ASR）

**缺点**：
- ❌ 需要 API Key 和费用
- ❌ 数据上传到云端

**配置示例**：
```ini
ASR_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-xxx...
ASR_MODEL=paraformer-v2  # 可选：paraformer-v2, fun-asr 等
```

**使用场景**：
- 需要快速处理大量视频
- 对准确率要求高
- 有预算支持

---

### Local（本地）配置

**优点**：
- ✅ 完全免费
- ✅ 数据隐私，不上传
- ✅ 无需网络连接
- ✅ 支持多种语言

**缺点**：
- ❌ 处理速度慢（CPU 模式）
- ❌ 需要下载模型文件（首次使用）
- ❌ 占用本地资源

**安装 Whisper**：
```bash
# 使用 uv
uv add openai-whisper

# 或使用 pip
pip install openai-whisper
```

**配置示例**：
```ini
ASR_PROVIDER=local
# 不需要 DASHSCOPE_API_KEY
```

**使用场景**：
- 处理敏感内容
- 预算有限
- 有 GPU 资源
- 离线环境

---

## 💡 使用建议

### 推荐配置

**日常使用**：
```ini
ASR_PROVIDER=dashscope  # 快速、准确
```

**隐私敏感**：
```ini
ASR_PROVIDER=local  # 完全本地处理
```

**混合使用**：
```bash
# 配置文件设为 dashscope（默认）
ASR_PROVIDER=dashscope

# 需要隐私时临时用 local
.\run.ps1 extract "链接" --asr-provider local
```

---

## 🔍 检查当前配置

运行配置检查命令：

```bash
.\run.ps1 config-check
```

输出示例：
```
ASR 配置:
  提供商: DashScope（云端） (dashscope)
  模型: paraformer-v2
  最大视频时长: 600秒
```

---

## ⚠️ 注意事项

### DashScope 使用注意

1. **API Key 安全**：不要将 `.env` 文件提交到 Git
2. **费用控制**：注意账户余额，避免超额
3. **网络要求**：需要稳定的网络连接

### Local 使用注意

1. **首次使用**：需要下载模型文件（base 模型约 150MB）
2. **硬件要求**：
   - CPU 模式：较慢，适合短视频
   - GPU 模式：快速，需要 CUDA 支持
3. **内存占用**：base 模型约占用 1GB 内存

---

## 🐛 常见问题

### Q: 如何切换 ASR 提供商？

**A**: 
1. 修改 `.env` 文件中的 `ASR_PROVIDER`
2. 或使用命令行参数 `--asr-provider`

### Q: Local 模式很慢怎么办？

**A**: 
1. 使用 GPU 加速（需要安装 CUDA）
2. 使用更小的模型（tiny/base）
3. 考虑使用 DashScope

### Q: 可以同时支持两种方式吗？

**A**: 可以！通过命令行参数临时覆盖配置文件设置。

---

## 📚 相关文档

- [环境变量配置指南](ENV_CONFIG_GUIDE.md)
- [Whisper 官方文档](https://github.com/openai/whisper)
- [DashScope 官方文档](https://help.aliyun.com/zh/model-studio/)

---

**更新时间**：2026-01-09  
**版本**：v1.0
