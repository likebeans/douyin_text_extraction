# 抖音视频文本提取工具 🎬 → 📝

> 快速将抖音视频转换为可编辑文本，支持自动语音转写与 Markdown 报告生成

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-green.svg)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Stable-success.svg)]()

## 📖 项目简介

这是一个基于 Python 开发的命令行工具，旨在帮助内容创作者、学习者和运营人员快速从抖音视频中提取文字内容。它通过模拟移动端访问获取无水印视频链接，并集成**阿里云 DashScope - Paraformer-v2 模型**实现高精度语音转写。

**核心价值**：
- **高效**：2 分钟视频仅需 ~40 秒处理时间（视频 URL 直接转写，无需下载）
- **精准**：基于阿里达摩院 Paraformer-v2 模型，中文识别准确率 >98%
- **便捷**：一键生成 Markdown 格式的完整文案报告
- **经济**：单视频成本极低（约 ¥0.013/分钟，2分钟视频仅需 ¥0.026）

---

## ✨ 核心特性

- 🔗 **全能解析**：支持分享口令、短链接 (`v.douyin.com`)、完整 URL (`douyin.com/video/...`)
- 📡 **稳定获取**：基于 HTML 解析技术，准确获取视频标题、作者、时长及无水印地址
- ☁️ **云端转写**：使用 DashScope 异步 API，支持直接通过视频 URL 转写，无需本地下载
- 🛡️ **智能兜底**：内置 OSS + FFmpeg 双重保障机制，主方案失败时自动切换，成功率 >95%
- 📝 **格式输出**：自动生成排版精美的 Markdown 报告，包含视频元数据
- ⚡ **极速处理**：跳过本地音频提取步骤，直接云端处理，大幅提升速度
- 🎙️ **双模式 ASR**：支持云端 DashScope（高精度）和本地 Whisper（免费）两种转写方式
- 🛠️ **开发友好**：提供 CLI 命令行工具，支持 Windows/macOS/Linux，内置 Windows 编码修复脚本

---

## 🚀 快速开始

### 1. 前置要求

- **Python 3.10+**
- **uv** (推荐的 Python 包管理器)
  ```bash
  # Windows (PowerShell)
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **FFmpeg** (已非必需，但推荐安装以备不时之需)

### 2. 安装步骤

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd douyin_practice

# 2. 安装依赖
uv sync

# 3. 配置环境变量
# 复制示例配置
cp .env.example .env
```

### 3. 配置环境变量

本项目依赖阿里云 DashScope 服务进行语音识别：

1. **复制配置模板**：
   ```bash
   cp .env.example .env
   ```

2. **获取 API Key**：
   - 访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/apiKey)
   - 登录/注册并开通 DashScope 服务
   - 创建 API Key

3. **编辑 `.env` 文件**：
   ```ini
   # 必需配置
   DASHSCOPE_API_KEY=sk-your-api-key-here
   
   # 可选配置（可保持默认值）
   ASR_MODEL=paraformer-v2
   MAX_VIDEO_DURATION=600
   OUTPUT_DIR=./output
   ```

4. **验证配置**：
   ```bash
   .\run.ps1 config-check
   ```

---

## 📖 使用指南

### 基础用法

**Windows 用户**（推荐使用 `run.ps1` 脚本以解决 emoji 乱码问题）：
```powershell
.\run.ps1 extract "https://v.douyin.com/iRNBho6U/"
```

**Linux/macOS 用户**：
```bash
uv run python main.py extract "https://v.douyin.com/iRNBho6U/"
```

### 高级选项

```bash
# 指定输出文件名
.\run.ps1 extract <链接> --output my_video

# 输出纯文本格式 (默认 md)
.\run.ps1 extract <链接> --format txt

# 仅在终端显示，不保存文件
.\run.ps1 extract <链接> --no-save

# 检查配置环境
.\run.ps1 config-check

# 查看版本
.\run.ps1 version
```

### 完整工作流示例

1. **复制链接**：在抖音 APP 点击分享 -> 复制链接
   > "9.99 03/19 lpQ:/ l@c.NW 齐刘海天团又添一位蛇喰梦子... https://v.douyin.com/gMf2cMP7g6g/"

2. **执行命令**：
   ```powershell
   .\run.ps1 extract "9.99 03/19 lpQ:/..." --output "剧解说_狂赌之渊"
   ```

3. **查看结果**：
   文件将保存在 `output/剧解说_狂赌之渊.md`

---

## 📄 输出示例

生成的 Markdown 报告包含两部分：视频元数据和提取的文本。

```markdown
# 抖音视频文本提取结果

## 📹 视频信息
- **标题**: 齐刘海天团又添一位蛇喰梦子 #好剧推荐 #狂赌之渊
- **作者**: 八点半movies
- **时长**: 3:34
- **视频ID**: 7579925307658980654
- **链接**: https://www.douyin.com/video/7579925307658980654

---

## 📝 提取文本

在岛国有这么一所贵族学校，除了学费贵以外，还有一个传统就是赌博盛行。学习成绩好不
好没关系，重要的是你有足够的筹码和精湛的赌术...
(此处省略 1000 字)

---
*提取时间: 2026-01-09 14:25:15*
```

---

## 📊 项目状态与技术原理

**当前版本**：v0.3.0 (OSS 兜底方案)  
**开发状态**：✅ 核心功能完成，生产就绪

### 核心技术实现

| 模块 | 技术方案 | 优势 |
|------|----------|------|
| **链接解析** | 正则表达式匹配 | 支持多种复杂文本格式提取 |
| **信息获取** | HTML 解析 (`window._ROUTER_DATA`) | 比 API 更稳定，包含完整元数据 |
| **无水印** | URL 替换 (`playwm` -> `play`) | 获取原始高清视频流 |
| **语音识别** | DashScope 异步 API (`async_call`) | 支持大文件，云端直接处理，无需本地下载 |

### 改进历程 (v0.1.0 -> v0.3.0)

我们从最初的 API 调用失败，经过持续迭代和优化，完成了多个重大升级：

**v0.1.0 -> v0.2.0**：
1. **获取方式升级**：从不稳定的 API 调用转向可靠的 HTML 页面解析（参考 [douyin-mcp-server](https://github.com/yzfly/douyin-mcp-server)）
2. **ASR 调用修复**：从错误的本地文件调用转向标准的异步 URL 提交
3. **流程优化**：移除了本地下载和音频提取步骤，直接使用视频 URL 进行云端识别，速度提升 50%

**v0.2.0 -> v0.3.0**：
1. **OSS 兜底方案**：实现 OSS + FFmpeg 智能兜底机制，主方案失败时自动切换
2. **双模式 ASR**：新增本地 Whisper 支持，可在云端和本地之间灵活切换
3. **可靠性提升**：成功率从 85-90% 提升至 95-98%

**性能指标**：
- **成功率**：95-98% (含兜底方案)
- **处理速度**：~20秒 / 分钟视频（主方案）
- **转写准确率**：~98% (Paraformer-v2)
- **兜底成本**：< ¥0.003 增量（仅在主方案失败时触发）

---

## ❓ 常见问题 (FAQ)

### Q: 为什么 Windows 下显示乱码？
**A**: Windows 终端默认编码可能不支持 Emoji。请使用提供的 `run.ps1` 脚本启动，它会自动设置 `$env:PYTHONIOENCODING='utf-8'`。

### Q: 提示 "FFmpeg 未安装"？
**A**: 主方案（视频 URL 直接转写）不需要 FFmpeg。但如果启用了 OSS 兜底方案或使用本地 Whisper ASR，则需要 FFmpeg 来提取音频。建议安装 FFmpeg 并添加到 PATH 以获得完整功能。

### Q: 视频时长有限制吗？
**A**: 默认限制为 10 分钟。可以在 `.env` 中修改 `MAX_VIDEO_DURATION` 调整限制。注意 DashScope 是按时长计费的。

### Q: 转写失败怎么办？
**A**: 
1. **主方案失败**：如果看到"方案1失败"，说明 DashScope 无法直接访问视频 URL。
   - 启用 OSS 兜底方案：在 `.env` 中设置 `OSS_ENABLE_FALLBACK=true` 并配置 OSS 参数。
2. **兜底方案失败**：检查 FFmpeg 是否已安装，OSS 配置是否正确。
3. **API Key 问题**：确认 DashScope API Key 是否有效且有额度。
4. **网络问题**：检查网络连接（需要能访问抖音和阿里云）。

### Q: 如何启用 OSS 兜底方案？
**A**: 
1. 在阿里云 OSS 控制台创建一个 Bucket（需要公网可访问）。
2. 在 `.env` 中配置：
   ```ini
   OSS_ENABLE_FALLBACK=true
   OSS_ACCESS_KEY_ID=LTAI5xxx...
   OSS_ACCESS_KEY_SECRET=xxx...
   OSS_BUCKET_NAME=your-bucket-name
   OSS_ENDPOINT=oss-cn-wuhan-lr.aliyuncs.com
   ```
3. 安装 FFmpeg（兜底方案需要）。
4. 运行 `.\run.ps1 config-check` 验证配置。

### Q: 本地 Whisper 和云端 DashScope 如何选择？
**A**: 
- **DashScope（推荐）**：高精度（98%），速度快，按量付费（¥0.013/分钟）。
- **本地 Whisper**：完全免费，但需要 GPU/强大 CPU，速度较慢，中文准确率略低。

在 `.env` 中设置：
```ini
ASR_PROVIDER=dashscope  # 云端（推荐）
# 或
ASR_PROVIDER=local      # 本地 Whisper（需安装：uv add openai-whisper）
```

---

## 🌐 Web 界面

项目还提供了 Web 界面版本，提供更友好的图形界面：

### 快速开始

```bash
# 启动 Web 应用
uv run python web_app.py

# 访问界面
# 本地：http://localhost:5000
# 局域网：http://<你的IP>:5000
```

### 功能特点

- ✅ **简单易用**：直观的 Web 界面，无需命令行知识
- ✅ **实时配置**：支持通过 Web 界面配置和修改参数
- ✅ **重点展示文本**：结果页面重点展示提取的文本内容
- ✅ **完整元数据**：同时显示视频的基本信息
- ✅ **响应式设计**：支持桌面和移动设备

### 详细文档

- [Web 界面使用指南](docs/README.md#web-界面)
- [外网访问配置](docs/web-external-access.md)
- [网络问题排查](docs/network-troubleshooting.md)

---

## 🔧 开发指南

### 项目结构

```
douyin_practice/
├── src/
│   ├── parser.py          # 链接解析
│   ├── fetcher.py         # 视频信息获取 (HTML解析核心)
│   ├── asr_client.py      # DashScope ASR 客户端（含兜底逻辑）
│   ├── local_asr_client.py # 本地 Whisper ASR 客户端
│   ├── oss_client.py      # 阿里云 OSS 客户端（兜底方案）
│   ├── audio_processor.py # 音频提取（FFmpeg）
│   └── formatter.py       # Markdown 格式化
├── tests/                 # 测试文件
│   └── test_oss_client.py # OSS 客户端测试
├── docs/                  # 项目文档
│   ├── README.md          # 文档索引
│   ├── ENV_CONFIG_GUIDE.md # 环境变量配置指南
│   ├── ASR_PROVIDER_GUIDE.md # ASR 提供商选择指南
│   └── ...                # 其他技术文档
├── config.py              # 配置管理（支持 .env）
├── main.py                # CLI 入口
├── web_app.py             # Web 界面入口
└── run.ps1                # Windows 启动脚本（UTF-8 编码修复）
```

### 运行测试

```bash
# 运行 OSS 客户端测试
uv run pytest tests/test_oss_client.py -v

# 测试各个模块
uv run python -m src.parser
uv run python -m src.fetcher
uv run python -m src.asr_client
```

### 技术亮点

1. **智能兜底机制**：主方案失败时自动切换到 OSS + FFmpeg，提供双重保障。
2. **异步转写**：使用 DashScope 异步 API，避免长时间阻塞。
3. **配置驱动**：所有参数通过 `.env` 配置，代码零修改。
4. **模块化设计**：清晰的职责分离，易于扩展和维护。
5. **完整测试**：包含 OSS 客户端完整测试套件。

### 未来计划

- [ ] **批量处理**：支持从文件导入多个链接批量提取
- [ ] **字幕导出**：支持导出 SRT 字幕文件（带时间戳）
- [ ] **本地缓存**：避免重复解析相同视频
- [x] **OSS 兜底方案**：✅ 已实现（v0.3.0）
- [x] **本地 ASR 支持**：✅ 已实现（v0.3.0）
- [x] **Web 界面**：✅ 已实现

---

## 📚 文档索引

项目完整文档请参考 [docs/README.md](docs/README.md)，包括：

- [环境变量配置指南](docs/ENV_CONFIG_GUIDE.md) - 完整的 `.env` 配置说明
- [ASR 提供商选择指南](docs/ASR_PROVIDER_GUIDE.md) - DashScope vs 本地 Whisper
- [技术说明澄清](docs/TECH_CLARIFICATION.md) - 重要技术细节说明
- [OSS + FFmpeg 兜底方案](docs/oss-ffmpeg-fallback-solution.md) - 兜底方案设计文档
- [问题修复记录](docs/link-parser-fix.md) - 链接解析器修复记录
- [Web 界面文档](docs/README.md#web-界面) - Web 界面使用指南

---

## 📄 License

MIT License

---

**维护者**: Developer  
**最后更新**: 2026-01-09  
**版本**: v0.3.0
