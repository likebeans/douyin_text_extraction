---
planStatus:
  planId: plan-oss-ffmpeg-fallback
  title: OSS + FFmpeg 兜底方案实现
  status: ready-for-development
  planType: feature
  priority: high
  owner: developer
  tags:
    - reliability
    - fallback
    - oss
    - ffmpeg
  created: "2026-01-09"
  updated: "2026-01-09T14:30:00.000Z"
  progress: 0
---

# OSS + FFmpeg 兜底方案实现

## 目标

- 实现 OSS + FFmpeg 作为 DashScope 转写的兜底方案
- 提升系统成功率从 85-90% 到 95-98%
- 保持成本增加在合理范围内（< ¥0.001/视频）
- 不影响现有的直接 URL 转写流程

## 项目概述

当前项目使用视频 URL 直接传给 DashScope 进行转写，但存在以下问题：

1. **视频 URL 失效**：抖音视频链接可能过期或失效
2. **网络问题**：DashScope 无法访问某些视频 URL
3. **防盗链限制**：某些视频可能有访问限制

**解决方案**：实现 OSS + FFmpeg 兜底机制，当直接 URL 方式失败时，自动降级到本地处理。

---

## 技术架构

### 方案对比

| 步骤 | 主方案（现有） | 兜底方案（新增） |
|------|---------------|----------------|
| 1 | 获取视频 URL | 获取视频 URL |
| 2 | 直接传给 DashScope | **下载视频到本地** |
| 3 | 云端转写 | **FFmpeg 提取音频** |
| 4 | 返回结果 | **上传音频到 OSS** |
| 5 | - | **OSS URL → DashScope** |
| 6 | - | **转写完成，删除临时文件** |

### 流程图

```
开始
  ↓
获取视频信息（fetcher.py）
  ↓
尝试方案1：直接 URL 转写
  ↓
成功? ──是──→ 返回结果
  ↓ 否
启动兜底方案
  ↓
下载视频 → FFmpeg 提取音频 → 上传到 OSS
  ↓
使用 OSS URL 转写
  ↓
成功? ──是──→ 清理临时文件 → 返回结果
  ↓ 否
返回失败
```

---

## 实现细节

### 1. 依赖包添加

```toml
# pyproject.toml
dependencies = [
    # ... 现有依赖 ...
    "oss2>=2.18.0",           # 阿里云 OSS SDK
    "requests>=2.31.0",       # 已有，用于下载视频
]
```

### 2. 配置管理

```python
# config.py - 新增配置项
class Settings(BaseSettings):
    # 现有配置 ...
    dashscope_api_key: str = ""
    
    # OSS 配置（新增）
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket_name: str = "jc-dev1"
    oss_endpoint: str = "oss-cn-wuhan-lr.aliyuncs.com"
    oss_enable_fallback: bool = True  # 是否启用兜底方案
    
    # 临时文件配置（新增）
    temp_dir: Path = Path("./temp")  # 临时文件目录
    cleanup_temp_files: bool = True  # 是否自动清理临时文件
```

**环境变量示例** (`.env`):

```ini
# DashScope API
DASHSCOPE_API_KEY=sk-xxx...

# 阿里云 OSS 配置
OSS_ACCESS_KEY_ID=LTAI5xxx...
OSS_ACCESS_KEY_SECRET=xxx...
OSS_BUCKET_NAME=jc-dev1
OSS_ENDPOINT=oss-cn-wuhan-lr.aliyuncs.com
OSS_ENABLE_FALLBACK=true
```

### 3. 新建 OSS 客户端模块

**文件**: `src/oss_client.py`

```python
"""阿里云 OSS 客户端模块"""
import oss2
from pathlib import Path
from typing import Optional
from datetime import datetime
from rich.console import Console

console = Console()


class OSSClient:
    """阿里云 OSS 客户端
    
    用于上传音频文件到 OSS，获取公网 URL 供 DashScope 使用
    """
    
    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        endpoint: str
    ):
        """初始化 OSS 客户端
        
        Args:
            access_key_id: 阿里云 AccessKey ID
            access_key_secret: 阿里云 AccessKey Secret
            bucket_name: OSS Bucket 名称
            endpoint: OSS Endpoint（如：oss-cn-wuhan-lr.aliyuncs.com）
        """
        self.bucket_name = bucket_name
        
        # 创建认证对象
        auth = oss2.Auth(access_key_id, access_key_secret)
        
        # 创建 Bucket 对象
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
    
    def upload_audio(
        self,
        local_file: Path,
        remote_path: Optional[str] = None
    ) -> Optional[str]:
        """上传音频文件到 OSS
        
        Args:
            local_file: 本地音频文件路径
            remote_path: OSS 中的存储路径（不指定则自动生成）
            
        Returns:
            公网访问 URL，失败返回 None
        """
        console.print("[cyan]📤 上传音频到 OSS...[/cyan]")
        
        if not local_file.exists():
            console.print(f"[red]❌ 本地文件不存在: {local_file}[/red]")
            return None
        
        try:
            # 生成远程路径（使用时间戳避免冲突）
            if not remote_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                remote_path = f"douyin_audio/{timestamp}_{local_file.name}"
            
            # 上传文件
            console.print(f"[dim]   本地文件: {local_file}[/dim]")
            console.print(f"[dim]   OSS 路径: {remote_path}[/dim]")
            
            with open(local_file, 'rb') as f:
                result = self.bucket.put_object(remote_path, f)
            
            if result.status != 200:
                console.print(f"[red]❌ 上传失败，状态码: {result.status}[/red]")
                return None
            
            # 生成公网访问 URL
            public_url = f"https://{self.bucket_name}.{self.bucket.endpoint}/{remote_path}"
            
            console.print(f"[green]✅ 上传成功[/green]")
            console.print(f"[dim]   公网 URL: {public_url[:80]}...[/dim]")
            
            return public_url
            
        except oss2.exceptions.OssError as e:
            console.print(f"[red]❌ OSS 错误: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ 上传失败: {e}[/red]")
            return None
    
    def delete_file(self, remote_path: str) -> bool:
        """删除 OSS 文件
        
        Args:
            remote_path: OSS 文件路径
            
        Returns:
            是否删除成功
        """
        try:
            self.bucket.delete_object(remote_path)
            console.print(f"[dim]>> 已删除 OSS 文件: {remote_path}[/dim]")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠ 删除 OSS 文件失败: {e}[/yellow]")
            return False
```

### 4. 增强 AudioProcessor

**文件**: `src/audio_processor.py`（修改）

添加视频下载功能：

```python
def download_video(self, video_url: str, save_path: Path) -> Optional[Path]:
    """下载视频到本地
    
    Args:
        video_url: 视频 URL
        save_path: 保存路径
        
    Returns:
        下载后的文件路径，失败返回 None
    """
    console.print(f"[cyan]📥 下载视频...[/cyan]")
    
    try:
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(save_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # 显示进度
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        console.print(f"[dim]   进度: {percent:.1f}%[/dim]", end='\r')
        
        console.print(f"[green]✅ 视频下载完成（{total_size / (1024*1024):.2f} MB）[/green]")
        return save_path
        
    except Exception as e:
        console.print(f"[red]❌ 视频下载失败: {e}[/red]")
        return None
```

### 5. 修改 ASRClient（核心逻辑）

**文件**: `src/asr_client.py`（修改）

添加兜底逻辑：

```python
def transcribe_with_fallback(
    self,
    video_url: str,
    video_id: str,
    settings  # 传入 settings 对象
) -> Optional[str]:
    """带兜底方案的转写
    
    Args:
        video_url: 视频 URL
        video_id: 视频 ID
        settings: 配置对象
        
    Returns:
        转写文本，失败返回 None
    """
    # 方案1: 尝试直接 URL 转写
    console.print("[cyan]🎯 方案1：直接 URL 转写[/cyan]")
    text = self.transcribe(video_url=video_url)
    
    if text:
        console.print("[green]✅ 方案1 成功[/green]")
        return text
    
    # 方案2: 兜底方案（OSS + FFmpeg）
    if not settings.oss_enable_fallback:
        console.print("[yellow]⚠ 兜底方案未启用[/yellow]")
        return None
    
    console.print("[yellow]⚠ 方案1 失败，启动兜底方案...[/yellow]")
    console.print("[cyan]🎯 方案2：OSS + FFmpeg 兜底[/cyan]")
    
    # 导入必要的模块
    from src.audio_processor import AudioProcessor
    from src.oss_client import OSSClient
    import tempfile
    
    temp_video = None
    temp_audio = None
    oss_path = None
    
    try:
        # 1. 下载视频
        settings.temp_dir.mkdir(parents=True, exist_ok=True)
        temp_video = settings.temp_dir / f"{video_id}.mp4"
        
        processor = AudioProcessor()
        if not processor.download_video(video_url, temp_video):
            return None
        
        # 2. 提取音频
        temp_audio = processor.extract_audio(temp_video)
        if not temp_audio:
            return None
        
        # 3. 上传到 OSS
        oss_client = OSSClient(
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            bucket_name=settings.oss_bucket_name,
            endpoint=settings.oss_endpoint
        )
        
        oss_url = oss_client.upload_audio(temp_audio)
        if not oss_url:
            return None
        
        # 记录 OSS 路径用于后续删除
        oss_path = oss_url.split(f"{settings.oss_bucket_name}.{settings.oss_endpoint}/")[1]
        
        # 4. 使用 OSS URL 转写
        text = self.transcribe(video_url=oss_url)
        
        if text:
            console.print("[green]✅ 方案2 成功[/green]")
        
        return text
        
    finally:
        # 5. 清理临时文件和 OSS 文件
        if settings.cleanup_temp_files:
            if temp_video and temp_video.exists():
                temp_video.unlink()
                console.print("[dim]>> 已删除临时视频文件[/dim]")
            
            if temp_audio and temp_audio.exists():
                temp_audio.unlink()
                console.print("[dim]>> 已删除临时音频文件[/dim]")
        
        # 删除 OSS 文件
        if oss_path:
            try:
                oss_client = OSSClient(
                    access_key_id=settings.oss_access_key_id,
                    access_key_secret=settings.oss_access_key_secret,
                    bucket_name=settings.oss_bucket_name,
                    endpoint=settings.oss_endpoint
                )
                oss_client.delete_file(oss_path)
            except:
                pass
```

### 6. 修改主程序

**文件**: `main.py`（修改）

```python
# 原来的代码（第 77 行）：
text = asr_client.transcribe(video_url=metadata.video_url)

# 改为：
text = asr_client.transcribe_with_fallback(
    video_url=metadata.video_url,
    video_id=video_id,
    settings=settings
)
```

---

## 验收标准

- [ ] 主方案成功时，不使用兜底方案
- [ ] 主方案失败时，自动启用兜底方案
- [ ] OSS 配置正确时，音频能成功上传
- [ ] 转写完成后，临时文件和 OSS 文件自动清理
- [ ] 配置项 `OSS_ENABLE_FALLBACK=false` 可以禁用兜底方案
- [ ] `config-check` 命令能检测 OSS 配置是否正确
- [ ] 文档更新（README 新增 OSS 配置说明）
- [ ] 测试用例通过：
  - 直接 URL 转写成功
  - 直接 URL 失败，兜底方案成功
  - 兜底方案失败，返回错误

---

## 成本分析

### 单视频成本估算

| 项目 | 成本 | 说明 |
|------|------|------|
| DashScope 转写 | ¥0.025/分钟 | 2分钟视频 ≈ ¥0.05 |
| OSS 存储 | ¥0.00012/GB/小时 | 5MB 文件存储 1 小时 ≈ ¥0.0000006 |
| OSS 流量 | ¥0.5/GB | 5MB 下载 ≈ ¥0.0025 |
| **总计（兜底方案）** | **≈ ¥0.0525** | 仅增加 ¥0.0025 |

**结论**：兜底方案成本增加微乎其微（< 5%），完全可接受。

---

## 实施计划

### Phase 1: 基础设施（1-2小时）
- [ ] 添加 `oss2` 依赖
- [ ] 创建 `src/oss_client.py`
- [ ] 在 `config.py` 中添加 OSS 配置项
- [ ] 创建 `.env.example` 更新 OSS 配置说明

### Phase 2: 核心功能（2-3小时）
- [ ] 在 `audio_processor.py` 中添加 `download_video` 方法
- [ ] 在 `asr_client.py` 中实现 `transcribe_with_fallback` 方法
- [ ] 修改 `main.py` 调用新方法

### Phase 3: 测试与优化（1-2小时）
- [ ] 单元测试：OSS 上传/删除
- [ ] 集成测试：完整兜底流程
- [ ] 错误处理优化
- [ ] 日志记录优化

### Phase 4: 文档与发布（30分钟）
- [ ] 更新 README.md（OSS 配置说明）
- [ ] 更新版本号到 v0.3.0
- [ ] Git 提交并推送
- [ ] 验证生产环境配置

**总计时间**：约 5-8 小时

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| OSS 配置错误 | 兜底方案无法使用 | 提供详细配置文档，`config-check` 增加 OSS 检测 |
| 磁盘空间不足 | 下载视频失败 | 添加磁盘空间检查，大文件提前警告 |
| FFmpeg 未安装 | 无法提取音频 | `config-check` 强制检查 FFmpeg |
| 网络下载慢 | 用户体验差 | 添加进度条，超时设置为 60 秒 |

---

## 相关资源

- [阿里云 OSS Python SDK 文档](https://help.aliyun.com/document_detail/32026.html)
- [DashScope API 文档](https://help.aliyun.com/zh/dashscope/developer-reference/api-details)
- [FFmpeg 官方文档](https://ffmpeg.org/documentation.html)

---

## 更新日志

- **2026-01-09**: 初始计划创建
