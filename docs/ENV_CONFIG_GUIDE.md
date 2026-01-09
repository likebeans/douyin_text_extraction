# 环境变量配置指南

## 📋 概述

本项目使用 `.env` 文件管理所有敏感配置和可调参数，遵循最佳实践：
- ✅ **安全性**：API Key 不写入代码，避免泄露
- ✅ **灵活性**：无需修改代码即可调整配置
- ✅ **标准化**：符合 12-Factor App 规范

---

## 🚀 快速开始

### 1. 复制配置模板

```bash
cp .env.example .env
```

### 2. 编辑 `.env` 文件

```ini
# 必需：填入你的 DashScope API Key
DASHSCOPE_API_KEY=sk-your-api-key-here

# 可选：保持默认值即可
ASR_MODEL=paraformer-v2
MAX_VIDEO_DURATION=600
```

### 3. 验证配置

```bash
.\run.ps1 config-check
```

---

## 📝 完整配置说明

### 必需配置

#### DASHSCOPE_API_KEY

- **说明**：阿里云 DashScope API Key
- **类型**：字符串
- **默认值**：无（必须填写）
- **获取方式**：[DashScope 控制台](https://dashscope.console.aliyun.com/apiKey)

```ini
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

### ASR 模型配置

#### ASR_MODEL

- **说明**：语音识别模型选择
- **类型**：字符串
- **默认值**：`paraformer-v2`
- **可选值**：
  - `paraformer-v2`：中文（普通话）+ 英文，准确率高 ⭐**推荐**
  - `paraformer-v1`：旧版本
  - `paraformer-8k-v2`：8kHz 采样率优化版（适合电话录音）
  - `fun-asr`：支持多方言 + 歌唱识别
  - `fun-asr-mtl`：多语言版本（支持东南亚语言）

```ini
ASR_MODEL=paraformer-v2
```

**模型对比**：

| 模型 | 适用场景 | 价格 |
|------|---------|------|
| paraformer-v2 | 普通话视频（推荐） | ¥0.0132/分钟 |
| fun-asr | 方言、歌唱内容 | ¥0.0132/分钟 |
| paraformer-8k-v2 | 电话录音 | ¥0.0132/分钟 |

#### MAX_VIDEO_DURATION

- **说明**：最大视频时长限制（秒）
- **类型**：整数
- **默认值**：`600`（10分钟）
- **建议值**：300-1200

```ini
MAX_VIDEO_DURATION=600
```

---

### 输出配置

#### OUTPUT_DIR

- **说明**：输出文件目录
- **类型**：路径字符串
- **默认值**：`./output`

```ini
OUTPUT_DIR=./output
```

---

### 网络请求配置

#### REQUEST_TIMEOUT

- **说明**：HTTP 请求超时时间（秒）
- **类型**：整数
- **默认值**：`30`

```ini
REQUEST_TIMEOUT=30
```

#### RETRY_TIMES

- **说明**：失败重试次数
- **类型**：整数
- **默认值**：`3`

```ini
RETRY_TIMES=3
```

---

### OSS 兜底方案配置（可选）

当直接 URL 转写失败时，可以启用 OSS + FFmpeg 兜底方案。

#### OSS_ENABLE_FALLBACK

- **说明**：是否启用 OSS 兜底方案
- **类型**：布尔值
- **默认值**：`false`

```ini
OSS_ENABLE_FALLBACK=false
```

#### OSS_ACCESS_KEY_ID

- **说明**：阿里云 OSS AccessKey ID
- **类型**：字符串
- **默认值**：空
- **获取方式**：[阿里云 RAM 控制台](https://ram.console.aliyun.com/manage/ak)

```ini
OSS_ACCESS_KEY_ID=LTAI5txxxxxxxxxx
```

#### OSS_ACCESS_KEY_SECRET

- **说明**：阿里云 OSS AccessKey Secret
- **类型**：字符串
- **默认值**：空

```ini
OSS_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### OSS_BUCKET_NAME

- **说明**：OSS Bucket 名称
- **类型**：字符串
- **默认值**：空

```ini
OSS_BUCKET_NAME=your-bucket-name
```

#### OSS_ENDPOINT

- **说明**：OSS Endpoint（地域节点）
- **类型**：字符串
- **默认值**：空
- **示例**：
  - 北京：`oss-cn-beijing.aliyuncs.com`
  - 上海：`oss-cn-shanghai.aliyuncs.com`
  - 武汉（本地域）：`oss-cn-wuhan-lr.aliyuncs.com`

```ini
OSS_ENDPOINT=oss-cn-wuhan-lr.aliyuncs.com
```

---

### 临时文件配置

#### TEMP_DIR

- **说明**：临时文件目录
- **类型**：路径字符串
- **默认值**：`./temp`

```ini
TEMP_DIR=./temp
```

#### CLEANUP_TEMP_FILES

- **说明**：是否自动清理临时文件
- **类型**：布尔值
- **默认值**：`true`

```ini
CLEANUP_TEMP_FILES=true
```

---

## 🔒 安全最佳实践

### 1. 不要提交 .env 文件到 Git

`.env` 文件已被加入 `.gitignore`，确保不会被提交。

### 2. 定期更换密钥

建议每 3-6 个月更换一次 API Key 和 AccessKey。

### 3. 使用环境隔离

不同环境使用不同的配置文件：
- 开发环境：`.env`
- 测试环境：`.env.test`
- 生产环境：`.env.production`

### 4. 最小权限原则

OSS AccessKey 只授予必要的权限（读写指定 Bucket）。

---

## 🐛 常见问题

### Q: 修改 .env 后不生效？

**A**: 需要重启程序。配置在程序启动时加载。

### Q: 找不到 .env 文件？

**A**: 
```bash
# 检查文件是否存在
ls -la .env

# 如果不存在，从模板复制
cp .env.example .env
```

### Q: API Key 无效？

**A**: 
1. 检查 Key 是否完整复制
2. 确认 Key 未过期
3. 验证账户余额是否充足

### Q: OSS 配置不生效？

**A**: 
1. 确认 `OSS_ENABLE_FALLBACK=true`
2. 检查所有 OSS 配置项是否填写完整
3. 运行 `.\run.ps1 config-check` 验证

---

## 📚 参考文档

- [阿里云 DashScope 文档](https://help.aliyun.com/zh/model-studio/)
- [阿里云 OSS 文档](https://help.aliyun.com/zh/oss/)
- [12-Factor App 配置规范](https://12factor.net/config)

---

**更新时间**：2026-01-09  
**版本**：v1.0
