# 技术说明澄清文档

## 📌 重要澄清：Fun-ASR vs Paraformer

### 问题

之前的代码注释中混淆了 Fun-ASR 和 Paraformer，实际上它们是两个不同的模型系列。

### 实际使用的模型

**项目使用的是：Paraformer-v2**

```python
# config.py
asr_model: str = "paraformer-v2"
```

---

## 🔍 模型对比

| 特性 | Fun-ASR | Paraformer-v2（本项目使用） |
|------|---------|---------------------------|
| **模型归属** | 通义百聆 | 阿里达摩院 |
| **支持语言** | 中文（含多方言）、英文、日语 | 中文（普通话）、英文 |
| **采样率** | 任意 | 任意 |
| **文件大小** | ≤2GB，≤12小时 | ≤2GB，无时长限制 |
| **价格** | 0.00022元/秒 | 0.00022元/秒 |
| **特殊功能** | 支持歌唱识别（带 BGM） | - |

**价格换算**：0.00022元/秒 × 60秒 = **¥0.0132/分钟**

### 价格修正

- ❌ **错误**：之前文档中说的 ¥0.025/分钟
- ✅ **正确**：¥0.0132/分钟（约 ¥0.013/分钟）

---

## 🎯 Paraformer-v2 详细信息

### 基本信息

- **模型名称**：`paraformer-v2`
- **API 端点**：`dashscope.audio.asr.Transcription`
- **调用方式**：异步（`async_call` + `wait`）

### 支持的文件格式

```
aac, amr, avi, flac, flv, m4a, mkv, mov, 
mp3, mp4, mpeg, ogg, opus, wav, webm, wma, wmv
```

### 核心能力

1. **自动音频提取**
   - ✅ 支持直接传入视频 URL
   - ✅ 后台自动提取音频流
   - ✅ 无需本地 FFmpeg 处理

2. **异步处理流程**
   ```python
   # 1. 提交任务
   task = Transcription.async_call(
       model="paraformer-v2",
       file_urls=[video_url],
       language_hints=['zh', 'en']
   )
   
   # 2. 等待完成
   result = Transcription.wait(task=task.output.task_id)
   
   # 3. 下载结果
   transcription_url = result.output['results'][0]['transcription_url']
   json_data = request.urlopen(transcription_url).read()
   text = json.loads(json_data)['transcripts'][0]['text']
   ```

3. **性能指标**
   - 识别准确率：>98%（中文普通话）
   - 处理速度：~20秒/分钟视频
   - 并发支持：最多100个文件同时处理

---

## 📝 已修正的文件

### 1. `src/asr_client.py`

**修正内容**：
- 模块文档字符串：明确标注使用 Paraformer 模型
- 类文档字符串：详细说明 Paraformer-v2 的特性和价格
- API 调用流程说明

### 2. `config.py`

**修正内容**：
- 配置项注释：说明可选的 Paraformer 模型版本

### 3. `README.md`

**修正内容**：
- 项目简介：明确标注使用 Paraformer-v2 模型
- 核心价值：更新价格为 ¥0.013/分钟
- 添加成本计算示例

---

## 🔗 官方文档参考

- [阿里云 DashScope - 录音文件识别](https://help.aliyun.com/zh/model-studio/recording-file-recognition)
- [Paraformer API 参考](https://help.aliyun.com/zh/model-studio/paraformer-api)

---

## 💡 最佳实践

### 模型选择建议

1. **Paraformer-v2**（当前使用）
   - ✅ 适合：普通话视频、英文内容
   - ✅ 优势：准确率高、无时长限制
   
2. **Fun-ASR**（可选）
   - ✅ 适合：方言视频、多语言混合、歌唱内容
   - ✅ 优势：支持多种方言、可识别带 BGM 的歌曲

3. **Paraformer-8k-v2**（可选）
   - ✅ 适合：电话录音（8kHz 采样率）
   - ✅ 优势：针对低采样率优化

### 切换模型

如需切换模型，只需修改配置：

```python
# config.py 或 .env
asr_model: str = "fun-asr"  # 切换到 Fun-ASR
# 或
ASR_MODEL=fun-asr
```

---

**更新时间**：2026-01-09  
**文档版本**：v1.0
