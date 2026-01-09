"""音频提取模块"""
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


class AudioProcessor:
    """音频处理器 - 使用 FFmpeg 从视频提取音频"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir())
    
    def check_ffmpeg(self) -> bool:
        """检查 FFmpeg 是否已安装"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def extract_audio(self, video_url: str, output_path: Optional[Path] = None) -> Optional[Path]:
        """从视频 URL 提取音频
        
        Args:
            video_url: 视频播放地址
            output_path: 输出文件路径，如果为 None 则使用临时文件
            
        Returns:
            音频文件路径，失败返回 None
        """
        # 检查 FFmpeg
        if not self.check_ffmpeg():
            console.print("[red]❌ FFmpeg 未安装或不在 PATH 中[/red]")
            console.print("[yellow]   请访问 https://ffmpeg.org/ 下载安装 FFmpeg[/yellow]")
            return None
        
        console.print("[cyan]🎵 开始提取音频...[/cyan]")
        
        # 准备输出路径
        if output_path is None:
            output_path = self.temp_dir / f"douyin_audio_{Path(tempfile.mktemp()).name}.wav"
        
        try:
            # FFmpeg 命令：提取音频并转换为 16kHz 单声道 WAV
            command = [
                'ffmpeg',
                '-i', video_url,          # 输入视频 URL
                '-vn',                    # 不处理视频
                '-acodec', 'pcm_s16le',   # 音频编码：16位 PCM
                '-ar', '16000',           # 采样率：16kHz
                '-ac', '1',               # 声道：单声道
                '-y',                     # 覆盖输出文件
                str(output_path)
            ]
            
            # 执行命令（隐藏输出）
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120  # 最多等待 2 分钟
            )
            
            if result.returncode != 0:
                console.print(f"[red]❌ 音频提取失败[/red]")
                console.print(f"[dim]{result.stderr[:200]}[/dim]")
                return None
            
            # 检查文件是否生成
            if not output_path.exists() or output_path.stat().st_size == 0:
                console.print("[red]❌ 音频文件未生成或为空[/red]")
                return None
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            console.print(f"[green]✅ 音频提取完成 ({file_size_mb:.2f} MB)[/green]")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            console.print("[red]❌ 音频提取超时（>2分钟）[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ 音频提取异常: {e}[/red]")
            return None


if __name__ == "__main__":
    # 测试代码
    processor = AudioProcessor()
    
    # 检查 FFmpeg
    if processor.check_ffmpeg():
        print("✓ FFmpeg 已安装")
    else:
        print("✗ FFmpeg 未安装")
    
    # 测试音频提取（需要真实的视频 URL）
    # test_url = "https://example.com/video.mp4"
    # audio_path = processor.extract_audio(test_url)
    # if audio_path:
    #     print(f"音频文件: {audio_path}")
