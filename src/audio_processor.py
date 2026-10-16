"""Download video files and extract audio with FFmpeg."""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urljoin

import requests
from rich.console import Console

from src.media_url import is_platform_media_url

console = Console()
DEFAULT_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


class AudioProcessor:
    """Audio processing with bounded streaming downloads and safe temp files."""

    def __init__(
        self,
        temp_dir: Optional[Path] = None,
        cleanup: bool = True,
        timeout: int = 30,
        max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
        ffmpeg_timeout: int = 120,
        download_timeout: int = 300,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_download_bytes <= 0:
            raise ValueError("max_download_bytes must be greater than zero")
        self.temp_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
        self.cleanup = cleanup
        self.timeout = timeout
        if download_timeout <= 0:
            raise ValueError("download_timeout must be greater than zero")
        self.download_timeout = download_timeout
        self.max_download_bytes = max_download_bytes
        if ffmpeg_timeout <= 0:
            raise ValueError("ffmpeg_timeout must be greater than zero")
        self.ffmpeg_timeout = ffmpeg_timeout

    def check_ffmpeg(self) -> bool:
        """Return whether FFmpeg is available."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _close_response(response) -> None:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    def download_video(self, video_url: str, save_path: Path) -> Optional[Path]:
        """Stream a video to a temporary sibling, enforcing size and elapsed limits."""
        save_path = Path(save_path)
        console.print("[cyan]📥 下载视频...[/cyan]")
        console.print(f"[dim]   URL: {video_url[:80]}...[/dim]")
        response = None
        staging_path = None
        started = time.monotonic()
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            current_url = video_url
            for redirect_count in range(6):
                if not is_platform_media_url(current_url):
                    raise ValueError("拒绝下载非平台媒体地址")
                remaining = self.download_timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("视频下载超过总耗时限制")
                response = requests.get(
                    current_url, stream=True,
                    timeout=min(self.timeout, remaining), allow_redirects=False,
                )
                if response.status_code not in {301, 302, 303, 307, 308}:
                    break
                location = response.headers.get("Location")
                if not location or redirect_count == 5:
                    raise ValueError("视频下载重定向无效或超过限制")
                current_url = urljoin(current_url, location)
                response.close()
                response = None
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > self.max_download_bytes:
                        raise ValueError("视频大小超过下载限制")
                except (TypeError, ValueError) as exc:
                    if str(exc) == "视频大小超过下载限制":
                        raise
                    # Ignore malformed Content-Length and enforce the streamed limit.
            fd, staging_name = tempfile.mkstemp(prefix=".download-", suffix=".part", dir=save_path.parent)
            staging_path = Path(staging_name)
            downloaded = 0
            try:
                with os.fdopen(fd, "wb") as output:
                    for chunk in response.iter_content(chunk_size=8192):
                        if time.monotonic() - started > self.download_timeout:
                            raise TimeoutError("视频下载超过总耗时限制")
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if downloaded > self.max_download_bytes:
                            raise ValueError("视频大小超过下载限制")
                        output.write(chunk)
                        if time.monotonic() - started > self.download_timeout:
                            raise TimeoutError("视频下载超过总耗时限制")
                    output.flush()
                    os.fsync(output.fileno())
            except BaseException:
                # fdopen closes fd once entered; close the raw descriptor if setup failed.
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise
            if downloaded == 0:
                raise ValueError("视频下载失败或文件为空")
            os.replace(staging_path, save_path)
            staging_path = None
            console.print(f"[green]✅ 视频下载完成（{downloaded / (1024 * 1024):.2f} MB）[/green]")
            return save_path
        except requests.exceptions.RequestException as exc:
            console.print(f"[red]❌ 网络请求失败: {exc}[/red]")
            return None
        except (OSError, ValueError, TimeoutError) as exc:
            console.print(f"[red]❌ 视频下载失败: {exc}[/red]")
            return None
        except Exception as exc:
            console.print(f"[red]❌ 视频下载失败: {exc}[/red]")
            return None
        finally:
            if response is not None:
                self._close_response(response)
            if staging_path is not None:
                try:
                    staging_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def extract_audio(
        self,
        video_source: Union[str, Path],
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """Extract a 16 kHz mono WAV, moving it into place only on success."""
        if not self.check_ffmpeg():
            console.print("[red]❌ FFmpeg 未安装或不在 PATH 中[/red]")
            console.print("[yellow]   请访问 https://ffmpeg.org/ 下载安装 FFmpeg[/yellow]")
            return None

        console.print("[cyan]🎵 开始提取音频...[/cyan]")
        staging_path = None
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            if output_path is None:
                fd, destination_name = tempfile.mkstemp(
                    prefix="douyin_audio_", suffix=".wav", dir=self.temp_dir
                )
                os.close(fd)
                destination = Path(destination_name)
                destination.unlink()
            else:
                destination = Path(output_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
            fd, staging_name = tempfile.mkstemp(
                prefix=".audio-", suffix=".wav", dir=destination.parent
            )
            os.close(fd)
            staging_path = Path(staging_name)
            command = [
                "ffmpeg",
                "-i",
                str(video_source),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-y",
                str(staging_path),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=self.ffmpeg_timeout
            )
            if result.returncode != 0:
                console.print("[red]❌ 音频提取失败[/red]")
                console.print(f"[dim]{result.stderr[:200]}[/dim]")
                return None
            if not staging_path.exists() or staging_path.stat().st_size == 0:
                console.print("[red]❌ 音频文件未生成或为空[/red]")
                return None
            os.replace(staging_path, destination)
            staging_path = None
            console.print(
                f"[green]✅ 音频提取完成 ({destination.stat().st_size / (1024 * 1024):.2f} MB)[/green]"
            )
            return destination
        except subprocess.TimeoutExpired:
            console.print(f"[red]❌ 音频提取超时（>{self.ffmpeg_timeout}秒）[/red]")
            return None
        except (OSError, ValueError) as exc:
            console.print(f"[red]❌ 音频提取异常: {exc}[/red]")
            return None
        except Exception as exc:
            console.print(f"[red]❌ 音频提取异常: {exc}[/red]")
            return None
        finally:
            if staging_path is not None:
                try:
                    staging_path.unlink(missing_ok=True)
                except OSError:
                    pass
