---
planStatus:
  planId: plan-improve-douyin-api-integration
  title: 改进抖音 API 集成 - 基于 douyin-mcp-server 研究
  status: ready-for-development
  planType: refactor
  priority: high
  owner: developer
  tags:
    - api-integration
    - douyin
    - bug-fix
    - refactor
  created: "2026-01-09"
  updated: "2026-01-09T13:50:00.000Z"
  progress: 0
---

# 改进抖音 API 集成

## 📋 Goals

- ✅ 修复视频元数据获取失败的问题
- ✅ 实现稳定的视频信息解析
- ✅ 修复 ASR 语音识别 API 调用
- ✅ 完成完整的视频文本提取流程
- ✅ 确保测试视频链接能够成功处理

## 🔍 问题分析

### 当前实现的问题

**1. 视频元数据获取失败**
```
错误信息：❌ API 响应格式错误或视频不存在
原因：使用了错误的 API 端点和请求方式
```

**2. ASR API 调用失败**
```
错误信息：DECODE_ERROR
原因：使用了错误的 API 调用方式（Recognition 而非 Transcription）
```

### douyin-mcp-server 的成功实现

基于对 [douyin-mcp-server](https://github.com/yzfly/douyin-mcp-server) 的研究，发现关键实现细节：

**核心技术点：**

1. **API 端点**：
   ```
   https://www.iesdouyin.com/share/video/{video_id}
   ```
   而非直接的 JSON API

2. **数据提取方式**：
   ```python
   # 从 HTML 中提取嵌入的 JSON 数据
   pattern = r"window\._ROUTER_DATA\s*=\s*(.*?)</script>"
   ```

3. **JSON 数据路径**：
   ```python
   # 支持两种类型
   VIDEO_ID_PAGE_KEY = "video_(id)/page"
   NOTE_ID_PAGE_KEY = "note_(id)/page"  # 图文类型
   
   # 数据路径
   data = json_data["loaderData"][key]["videoInfoRes"]["item_list"][0]
   ```

4. **无水印视频链接**：
   ```python
   # 将 playwm 替换为 play
   video_url = url.replace("playwm", "play")
   ```

5. **ASR API 正确调用方式**：
   ```python
   # 异步提交任务
   task_response = dashscope.audio.asr.Transcription.async_call(
       model="paraformer-v2",
       file_urls=[video_url],
       language_hints=['zh', 'en']
   )
   
   # 等待任务完成
   transcription_response = dashscope.audio.asr.Transcription.wait(
       task=task_response.output.task_id
   )
   
   # 从 transcription_url 下载结果
   url = transcription_response.output['results'][0]['transcription_url']
   result = json.loads(request.urlopen(url).read().decode('utf8'))
   text = result['transcripts'][0]['text']
   ```

## 🛠️ Implementation Details

### Phase 1: 重写视频元数据获取模块 (fetcher.py)

**修改内容：**

```python
class DouyinFetcher:
    """抖音视频元数据获取器 - 基于 HTML 解析"""
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        # 使用移动端 User-Agent
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1'
        })
    
    def fetch(self, video_id: str) -> Optional[VideoMetadata]:
        """从 HTML 页面解析视频信息"""
        
        # 1. 构建分享 URL
        share_url = f'https://www.iesdouyin.com/share/video/{video_id}'
        
        # 2. 获取 HTML 内容
        response = self.session.get(share_url, timeout=self.timeout)
        response.raise_for_status()
        
        # 3. 提取 window._ROUTER_DATA JSON
        pattern = re.compile(
            pattern=r"window\._ROUTER_DATA\s*=\s*(.*?)</script>",
            flags=re.DOTALL,
        )
        match = pattern.search(response.text)
        
        if not match:
            raise ValueError("无法从 HTML 中提取数据")
        
        # 4. 解析 JSON 数据
        json_data = json.loads(match.group(1).strip())
        
        # 5. 处理两种类型（视频/图集）
        VIDEO_ID_PAGE_KEY = "video_(id)/page"
        NOTE_ID_PAGE_KEY = "note_(id)/page"
        
        if VIDEO_ID_PAGE_KEY in json_data["loaderData"]:
            original_info = json_data["loaderData"][VIDEO_ID_PAGE_KEY]["videoInfoRes"]
        elif NOTE_ID_PAGE_KEY in json_data["loaderData"]:
            original_info = json_data["loaderData"][NOTE_ID_PAGE_KEY]["videoInfoRes"]
        else:
            raise ValueError("无法识别的数据格式")
        
        # 6. 提取视频信息
        data = original_info["item_list"][0]
        video_url = data["video"]["play_addr"]["url_list"][0]
        
        # 7. 获取无水印链接
        video_url = video_url.replace("playwm", "play")
        
        # 8. 构建元数据
        metadata = VideoMetadata(
            video_id=video_id,
            title=data.get("desc", "").strip() or f"douyin_{video_id}",
            author=data.get("author", {}).get("nickname", "未知作者"),
            duration=data["video"].get("duration", 0) // 1000,
            video_url=video_url
        )
        
        return metadata
```

**改进要点：**
- ✅ 使用正确的 API 端点
- ✅ 从 HTML 解析嵌入的 JSON
- ✅ 处理两种内容类型（视频/图集）
- ✅ 正确提取无水印链接
- ✅ 添加详细的错误处理

### Phase 2: 修复 ASR 客户端 (asr_client.py)

**修改内容：**

```python
class ASRClient:
    """阿里云 DashScope ASR 客户端 - 使用异步 API"""
    
    def __init__(self, api_key: str, model: str = "paraformer-v2"):
        self.api_key = api_key
        self.model = model
        
        import dashscope
        self.dashscope = dashscope
        dashscope.api_key = api_key
    
    def transcribe(self, audio_path: Path = None, video_url: str = None) -> Optional[str]:
        """转写音频/视频为文本
        
        Args:
            audio_path: 本地音频文件路径（可选）
            video_url: 视频 URL（推荐，直接使用视频链接）
        """
        from http import HTTPStatus
        from urllib import request
        import json
        
        console.print("[cyan]🎤 开始语音识别...[/cyan]")
        
        try:
            # 优先使用视频 URL（无需下载和提取音频）
            file_url = video_url if video_url else f"file://{audio_path.absolute()}"
            
            # 1. 提交异步转写任务
            console.print("[dim]   提交转写任务...[/dim]")
            task_response = self.dashscope.audio.asr.Transcription.async_call(
                model=self.model,
                file_urls=[file_url],
                language_hints=['zh', 'en']
            )
            
            if task_response.status_code != HTTPStatus.OK:
                console.print(f"[red]❌ 提交任务失败: {task_response.message}[/red]")
                return None
            
            task_id = task_response.output.task_id
            console.print(f"[dim]   任务 ID: {task_id}[/dim]")
            
            # 2. 等待任务完成
            console.print("[dim]   等待转写完成...[/dim]")
            transcription_response = self.dashscope.audio.asr.Transcription.wait(
                task=task_id
            )
            
            if transcription_response.status_code != HTTPStatus.OK:
                console.print(f"[red]❌ 转写失败: {transcription_response.message}[/red]")
                return None
            
            # 3. 下载转写结果
            results = transcription_response.output['results']
            if not results:
                console.print("[red]❌ 没有转写结果[/red]")
                return None
            
            transcription_url = results[0]['transcription_url']
            console.print(f"[dim]   下载结果...[/dim]")
            
            result_json = json.loads(request.urlopen(transcription_url).read().decode('utf8'))
            
            # 4. 提取文本
            if 'transcripts' in result_json and result_json['transcripts']:
                text = result_json['transcripts'][0]['text']
                word_count = len(text)
                console.print(f"[green]✅ 语音识别完成（{word_count} 字）[/green]")
                return text
            else:
                console.print("[yellow]⚠ 未识别到文本内容[/yellow]")
                return "（音频中未检测到语音内容）"
        
        except Exception as e:
            console.print(f"[red]❌ ASR 调用异常: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return None
```

**改进要点：**
- ✅ 使用正确的异步 API（async_call + wait）
- ✅ 支持直接使用视频 URL（无需本地文件）
- ✅ 从 transcription_url 下载结果
- ✅ 详细的进度提示
- ✅ 完善的错误处理

### Phase 3: 优化主流程 (main.py)

**修改内容：**

```python
@app.command()
def extract(link: str, ...):
    """提取抖音视频的文本内容"""
    
    # ... 前面的代码 ...
    
    # 4. 提取音频（可选 - 如果 ASR 支持视频 URL 则跳过）
    # processor = AudioProcessor()
    # audio_path = processor.extract_audio(metadata.video_url)
    
    # 5. 语音识别（直接使用视频 URL）
    try:
        asr_client = ASRClient(settings.dashscope_api_key, settings.asr_model)
        
        # 优先使用视频 URL，无需下载和提取音频
        text = asr_client.transcribe(video_url=metadata.video_url)
        
        if not text:
            console.print("[red]❌ 语音识别失败[/red]")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]❌ 处理失败: {e}[/red]")
        raise typer.Exit(code=1)
    
    # ... 后续代码 ...
```

**改进要点：**
- ✅ 直接使用视频 URL 进行 ASR
- ✅ 跳过音频提取步骤（节省时间和空间）
- ✅ 简化错误处理流程

## ✅ Acceptance Criteria

### 功能验证

- [ ] **链接解析成功**
  - 提取视频 ID：`7570933456504326888`
  - 重定向处理正常

- [ ] **视频信息获取成功**
  - 获取真实的标题（而非"测试视频"）
  - 获取作者昵称
  - 获取视频时长
  - 获取无水印视频 URL

- [ ] **ASR 转写成功**
  - 提交任务成功
  - 等待任务完成
  - 下载并解析转写结果
  - 提取文本内容

- [ ] **完整流程测试**
  - 使用测试链接：`https://v.douyin.com/fRLvTT2lEUQ/`
  - 生成正确的 Markdown 报告
  - 保存到 `output/` 目录

### 代码质量

- [ ] 添加详细的错误处理
- [ ] 添加进度提示信息
- [ ] 代码注释完整
- [ ] 遵循现有代码风格

### 文档更新

- [ ] 更新 README 说明 API 变更
- [ ] 更新 USAGE_GUIDE 添加故障排查
- [ ] 更新 PROJECT_STATUS 记录改进

## 📊 Implementation Plan

### Task 1: 重写 fetcher.py（优先级：高）
**预计时间**：1-2 小时

- [ ] 备份当前 fetcher.py
- [ ] 实现新的 HTML 解析逻辑
- [ ] 添加正则提取 window._ROUTER_DATA
- [ ] 处理两种内容类型
- [ ] 实现无水印链接处理
- [ ] 添加错误处理
- [ ] 单元测试

### Task 2: 修复 asr_client.py（优先级：高）
**预计时间**：1-2 小时

- [ ] 备份当前 asr_client.py
- [ ] 实现异步 API 调用（async_call + wait）
- [ ] 支持视频 URL 直接转写
- [ ] 实现 transcription_url 下载
- [ ] 添加进度提示
- [ ] 添加详细错误处理
- [ ] 测试转写功能

### Task 3: 优化主流程（优先级：中）
**预计时间**：30 分钟

- [ ] 修改 main.py 使用视频 URL 直接转写
- [ ] 简化音频提取步骤（可选）
- [ ] 优化错误提示
- [ ] 测试完整流程

### Task 4: 测试与文档（优先级：中）
**预计时间**：30 分钟

- [ ] 使用真实链接测试完整流程
- [ ] 验证所有功能正常
- [ ] 更新 README 和 USAGE_GUIDE
- [ ] 更新 PROJECT_STATUS
- [ ] 记录已知问题和限制

## 🎯 Success Metrics

| 指标 | 目标 | 当前 | 验证方式 |
|------|------|------|----------|
| 链接解析成功率 | 100% | ✅ 100% | 测试多种链接格式 |
| 视频信息获取成功率 | > 95% | ❌ 0% | 使用真实视频链接测试 |
| ASR 转写成功率 | > 90% | ❌ 0% | 测试多个视频 |
| 完整流程成功率 | > 90% | ❌ 0% | 端到端测试 |
| 处理速度 | < 60s/分钟 | ⏱️ 待测 | 性能测试 |

## ⚠️ Risks & Mitigation

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 抖音 HTML 结构变化 | 高 | 高 | 添加多种解析策略，保留错误日志 |
| ASR API 调用限制 | 中 | 中 | 添加重试机制，错误提示 |
| 视频 URL 过期 | 低 | 中 | 缓存视频信息，提示用户重试 |
| 性能问题 | 低 | 低 | 优化异步处理，添加缓存 |

## 📚 References

- [douyin-mcp-server GitHub](https://github.com/yzfly/douyin-mcp-server)
- [阿里云 DashScope 文档](https://help.aliyun.com/zh/dashscope/)
- [Transcription API 文档](https://help.aliyun.com/zh/dashscope/developer-reference/api-details-9)

## 💡 Next Steps After Completion

- [ ] 添加批量处理支持
- [ ] 实现结果缓存机制
- [ ] 支持更多视频平台
- [ ] 添加 Web 界面
- [ ] 优化性能和成本

---

**创建时间**：2026-01-09  
**最后更新**：2026-01-09 13:50
**负责人**：Developer  
**状态**：✅ 就绪，可以开始实施
