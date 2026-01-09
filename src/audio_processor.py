"""音频提取模块"""
import subprocess
import tempfile
import requests
from pathlib import Path
from typing import Optional, Union
from rich.console import Console
from tqdm import tqdm

console = Console()


class AudioProcessor:
    """音频处理器 - 使用 FFmpeg 从视频提取音频"""
    
    def __init__(self, temp_dir: Optional[Path] = None, cleanup: bool = True):
        """初始化音频处理器
        
        Args:
            temp_dir: 临时文件目录，默认使用系统临时目录
            cleanup: 是否在处理完成后自动清理临时文件
        """
        self.temp_dir = temp_dir or Path(tempfile.gettempdir())
        self.cleanup = cleanup
    
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
    
    def download_video(self, video_url: str, save_path: Path) -> Optional[Path]:
        """下载视频到本地
        
        Args:
            video_url: 视频 URL
            save_path: 保存路径
            
        Returns:
            下载后的文件路径，失败返回 None
        """
        console.print(f"[cyan]📥 下载视频...[/cyan]")
        console.print(f"[dim]   URL: {video_url[:80]}...[/dim]")
        
        try:
            # 发送 GET 请求（流式下载）
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()
            
            # 获取文件总大小
            total_size = int(response.headers.get('content-length', 0))
            
            # 确保保存目录存在
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 下载文件并显示进度
            with open(save_path, 'wb') as f:
                if total_size == 0:
                    # 文件大小未知，直接下载
                    f.write(response.content)
                else:
                    # 显示进度条
                    with tqdm(total=total_size, unit='B', unit_scale=True, desc="   下载进度") as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
            
            # 验证文件
            if not save_path.exists() or save_path.stat().st_size == 0:
                console.print("[red]❌ 视频下载失败或文件为空[/red]")
                return None
            
            file_size_mb = save_path.stat().st_size / (1024 * 1024)
            console.print(f"[green]✅ 视频下载完成（{file_size_mb:.2f} MB）[/green]")
            return save_path
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ 网络请求失败: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ 视频下载失败: {e}[/red]")
            return None
    
    def extract_audio(self, video_source: Union[str, Path], output_path: Optional[Path] = None) -> Optional[Path]:
        """从视频提取音频
        
        Args:
            video_source: 视频来源（URL 或本地文件路径）
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
            # 确定输入源（URL 或本地文件）
            input_source = str(video_source)
            if isinstance(video_source, Path):
                console.print(f"[dim]   输入: 本地文件 {video_source.name}[/dim]")
            else:
                console.print(f"[dim]   输入: 视频 URL[/dim]")
            
            # FFmpeg 命令：提取音频并转换为 16kHz 单声道 WAV
            command = [
                'ffmpeg',
                '-i', input_source,       # 输入视频（URL 或本地路径）
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
