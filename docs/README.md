# 项目文档索引

本文档目录包含项目相关的所有技术文档、配置指南、问题记录和解决方案。

---

## 📚 文档分类

### 🚀 快速开始

- **[主项目 README](../README.md)** - 项目概述、安装、使用指南
- **[Web 界面使用指南](#web-界面)** - Web 界面详细说明（见下方）

### ⚙️ 配置指南

- **[环境变量配置指南](./ENV_CONFIG_GUIDE.md)** - 完整的 `.env` 配置说明
  - DashScope API Key 配置
  - OSS 兜底方案配置
  - ASR 模型选择
  - 临时文件管理

- **[ASR 提供商选择指南](./ASR_PROVIDER_GUIDE.md)** - DashScope vs 本地 Whisper
  - 两种方式对比
  - 配置方法
  - 使用场景建议
  - 常见问题

### 🔧 技术文档

- **[技术说明澄清](./TECH_CLARIFICATION.md)** - 重要技术细节说明
  - Fun-ASR vs Paraformer 模型区别
  - Paraformer-v2 详细信息
  - API 调用流程
  - 价格说明

- **[OSS + FFmpeg 兜底方案](./oss-ffmpeg-fallback-solution.md)** - 兜底方案设计文档
  - 技术架构
  - 实现细节
  - 成本分析
  - 验收标准

- **[抖音 API 集成改进](./improve-douyin-api-integration.md)** - API 集成优化记录
  - 问题分析
  - 解决方案
  - HTML 解析技术
  - 实现细节

### 🐛 问题修复记录

- **[链接解析器修复记录](./link-parser-fix.md)** - 短链接解析问题修复
  - 问题：无法解析包含下划线的抖音短链接
  - 修复日期：2026-01-09
  - 状态：✅ 已修复

### 🌐 Web 界面相关

- **[Web 界面外网访问配置](./web-external-access.md)** - 外网访问配置指南
  - 防火墙配置
  - 端口转发
  - 安全建议

- **[网络访问问题排查](./network-troubleshooting.md)** - 网络问题排查指南
  - HTTP 502 错误
  - 局域网 IP 识别
  - 防火墙配置

### 🛠️ 开发工具

- **[Git Worktree 与并行开发实战](./git-worktree-parallel-development.md)** - Git Worktree 使用指南
  - 基础概念
  - 实战案例
  - 最佳实践
  - 常见问题

---

## 📖 Web 界面

### 快速开始

1. **启动 Web 应用**：
   ```bash
   uv run python web_app.py
   ```

2. **访问界面**：
   - 本地：`http://localhost:5000`
   - 局域网：`http://<你的IP>:5000`

3. **配置 API Key**：
   - 访问 `http://localhost:5000/config`
   - 或创建 `.env` 文件

### 功能特点

- ✅ **简单易用**：直观的 Web 界面，无需命令行知识
- ✅ **实时配置**：支持通过 Web 界面配置和修改参数
- ✅ **重点展示文本**：结果页面重点展示提取的文本内容
- ✅ **完整元数据**：同时显示视频的基本信息
- ✅ **响应式设计**：支持桌面和移动设备

### 详细文档

- [外网访问配置](./web-external-access.md)
- [网络问题排查](./network-troubleshooting.md)

---

## 🔍 快速查找

### 按主题类型查找

| 主题 | 文档 |
|------|------|
| **配置问题** | [环境变量配置指南](./ENV_CONFIG_GUIDE.md) |
| **ASR 选择** | [ASR 提供商选择指南](./ASR_PROVIDER_GUIDE.md) |
| **技术细节** | [技术说明澄清](./TECH_CLARIFICATION.md) |
| **链接解析** | [链接解析器修复记录](./link-parser-fix.md) |
| **OSS 兜底** | [OSS + FFmpeg 兜底方案](./oss-ffmpeg-fallback-solution.md) |
| **API 集成** | [抖音 API 集成改进](./improve-douyin-api-integration.md) |
| **Web 访问** | [Web 界面外网访问配置](./web-external-access.md) |
| **网络问题** | [网络访问问题排查](./network-troubleshooting.md) |
| **Git 工作流** | [Git Worktree 与并行开发实战](./git-worktree-parallel-development.md) |

### 按问题类型查找

| 问题 | 文档 |
|------|------|
| 如何配置 API Key？ | [环境变量配置指南](./ENV_CONFIG_GUIDE.md) |
| 如何选择 ASR 提供商？ | [ASR 提供商选择指南](./ASR_PROVIDER_GUIDE.md) |
| 链接解析失败？ | [链接解析器修复记录](./link-parser-fix.md) |
| 转写失败怎么办？ | [OSS + FFmpeg 兜底方案](./oss-ffmpeg-fallback-solution.md) |
| Web 界面无法外网访问？ | [Web 界面外网访问配置](./web-external-access.md) |
| 网络连接问题？ | [网络访问问题排查](./network-troubleshooting.md) |

---

## 📝 文档规范

### 文档命名

- 使用小写字母和连字符：`link-parser-fix.md`
- 描述性命名，清晰表达文档内容
- 日期格式：YYYY-MM-DD

### 文档结构

每个技术文档应包含：

1. **概述** - 文档目的和适用范围
2. **快速开始** - 快速上手指南
3. **详细说明** - 完整的技术细节
4. **配置示例** - 实际配置示例
5. **常见问题** - FAQ 和故障排除
6. **相关文档** - 相关文档链接

---

## 📚 相关文档

### 项目文档

- [主项目 README](../README.md) - CLI 版本使用说明
- [PRD 文档](../PRD_Douyin_Video_Analyzer_MVP.md) - 产品需求文档

### 外部资源

- [阿里云 DashScope 文档](https://help.aliyun.com/zh/model-studio/)
- [阿里云 OSS 文档](https://help.aliyun.com/zh/oss/)
- [Whisper 官方文档](https://github.com/openai/whisper)
- [Git Worktree 官方文档](https://git-scm.com/docs/git-worktree)

---

**最后更新**: 2026-01-09  
**文档版本**: v1.0
