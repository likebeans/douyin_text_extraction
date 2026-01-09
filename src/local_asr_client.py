"""本地 ASR 客户端模块 - 使用 Whisper 进行语音识别"""
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


class LocalASRClient:
    """本地 ASR 客户端 - 使用 OpenAI Whisper 模型
    
    优势：
    - 完全免费，无需 API Key
    - 数据隐私，不上传到云端
    - 支持多种语言
    
    劣势：
    - 需要本地 GPU 或 CPU 资源
    - 处理速度较慢（CPU 模式）
    - 需要下载模型文件（首次使用）
    """
    
    def __init__(self, model: str = "base"):
        """
        Args:
            model: Whisper 模型大小
                可选值：tiny, base, small, medium, large
                模型越大，准确率越高，但速度越慢
        """
        self.model = model
        self._whisper = None
        self._load_whisper()
    
    def _load_whisper(self):
        """延迟加载 Whisper 库"""
        try:
            import whisper
            self._whisper = whisper
            console.print(f"[dim]   已加载 Whisper 模型: {self.model}[/dim]")
        except ImportError:
            console.print("[red]❌ whisper 库未安装[/red]")
            console.print("[yellow]   请运行: uv add openai-whisper[/yellow]")
            console.print("[yellow]   或: pip install openai-whisper[/yellow]")
            raise
    
    def transcribe(
        self,
        audio_path: Optional[Path] = None,
        video_url: Optional[str] = None
    ) -> Optional[str]:
        """转写音频/视频为文本
        
        Args:
            audio_path: 本地音频文件路径（推荐）
            video_url: 视频 URL（需要先下载）
            
        Returns:
            转写文本，失败返回 None
        """
        console.print("[cyan]🎤 开始本地语音识别（Whisper）...[/cyan]")
        
        # 优先使用本地音频文件
        if not audio_path and not video_url:
            console.print("[red]❌ 必须提供 audio_path 或 video_url[/red]")
            return None
        
        # 如果只有视频 URL，需要先下载（这里简化处理，建议先用 audio_processor 提取音频）
        if video_url and not audio_path:
            console.print("[yellow]⚠ 本地 ASR 需要本地音频文件[/yellow]")
            console.print("[yellow]   建议：先用 audio_processor 提取音频，再调用本地 ASR[/yellow]")
            return None
        
        if not audio_path.exists():
            console.print(f"[red]❌ 音频文件不存在: {audio_path}[/red]")
            return None
        
        try:
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            console.print(f"[dim]   文件大小: {file_size_mb:.2f} MB[/dim]")
            console.print(f"[dim]   使用模型: {self.model}[/dim]")
            console.print(f"[dim]   开始转写（这可能需要一些时间）...[/dim]")
            
            # 加载模型（首次使用会下载）
            model = self._whisper.load_model(self.model)
            
            # 转写音频
            result = model.transcribe(
                str(audio_path),
                language="zh",  # 指定中文，提高准确率
                task="transcribe"
            )
            
            # 提取文本
            text = result["text"].strip()
            word_count = len(text)
            
            console.print(f"[green]✅ 语音识别完成（{word_count} 字）[/green]")
            console.print(f"[dim]   预览: {text[:100]}{'...' if len(text) > 100 else ''}[/dim]")
            
            return text
            
        except Exception as e:
            console.print(f"[red]❌ 本地 ASR 调用异常: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return None


if __name__ == "__main__":
    # 测试代码
    import os
    
    # 测试本地音频文件转写
    test_audio = Path("test_audio.wav")
    if not test_audio.exists():
        print("❌ 请提供测试音频文件: test_audio.wav")
        exit(1)
    
    print("\n测试本地 Whisper 转写...")
    client = LocalASRClient(model="base")
    text = client.transcribe(audio_path=test_audio)
    
    if text:
        print(f"\n✅ 转写成功！")
        print(f"文本: {text[:200]}...")
    else:
        print("\n❌ 转写失败")
