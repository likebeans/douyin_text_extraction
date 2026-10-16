"""DashScope speech recognition client with bounded task polling."""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib import request
from urllib.parse import quote, urlsplit

from rich.console import Console

console = Console()


class ASRClient:
    """DashScope Paraformer client with explicit credentials and timeouts."""

    POLL_INTERVAL_SECONDS = 2

    def __init__(
        self,
        api_key: str,
        model: str = "paraformer-v2",
        request_timeout: int = 30,
        asr_timeout: int = 600,
    ):
        if request_timeout <= 0 or asr_timeout <= 0:
            raise ValueError("request_timeout and asr_timeout must be greater than zero")
        self.api_key = api_key
        self.model = model
        self.request_timeout = request_timeout
        self.asr_timeout = asr_timeout
        try:
            import dashscope
            from http import HTTPStatus

            self.dashscope = dashscope
            self.HTTPStatus = HTTPStatus
        except ImportError as exc:
            console.print("[red]❌ dashscope 库未安装，请运行: uv sync[/red]")
            raise ImportError("Install the cloud ASR dependencies with `uv sync`.") from exc

    @staticmethod
    def _field(value, key, default=None):
        if isinstance(value, dict):
            return value.get(key, default)
        getter = getattr(value, "get", None)
        if callable(getter):
            return getter(key, default)
        return getattr(value, key, default)

    def transcribe(
        self,
        audio_path: Optional[Path] = None,
        video_url: Optional[str] = None,
    ) -> Optional[str]:
        """Transcribe a remote HTTP(S) URL; local files require OSS upload first."""
        console.print("[cyan]🎤 开始语音识别...[/cyan]")
        if not video_url and not audio_path:
            console.print("[red]❌ 必须提供 video_url 或 audio_path[/red]")
            return None
        if video_url:
            file_url = video_url
            console.print("[dim]   使用视频 URL 进行转写[/dim]")
        else:
            console.print("[red]❌ 云端 ASR 不支持本地音频路径，请通过 OSS 兜底上传后转写[/red]")
            return None

        transcription = self.dashscope.audio.asr.Transcription
        deadline = time.monotonic() + self.asr_timeout
        try:
            console.print("[dim]   提交转写任务到 DashScope...[/dim]")
            task_response = transcription.async_call(
                model=self.model,
                file_urls=[file_url],
                language_hints=["zh", "en"],
                api_key=self.api_key,
                request_timeout=min(self.request_timeout, self.asr_timeout),
            )
            if task_response.status_code != self.HTTPStatus.OK:
                console.print(f"[red]❌ 提交任务失败，状态码: {task_response.status_code}[/red]")
                return None
            task_id = self._field(task_response.output, "task_id")
            if not task_id:
                console.print("[red]❌ DashScope 未返回任务 ID[/red]")
                return None
            console.print(f"[dim]   任务 ID: {task_id}[/dim]")

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    console.print("[red]❌ ASR 任务等待超时[/red]")
                    return None
                response_timeout = min(float(self.request_timeout), remaining)
                # SDK fetch() 固定使用其默认超时；直接查询任务以应用本次剩余期限。
                task_url = f"{self.dashscope.base_http_api_url.rstrip('/')}/tasks/{quote(str(task_id), safe='')}"
                task_request = request.Request(
                    task_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                )
                with request.urlopen(task_request, timeout=response_timeout) as task_result:
                    task_payload = json.loads(task_result.read().decode("utf-8"))
                output = task_payload.get("output", {}) if isinstance(task_payload, dict) else {}
                status = self._field(output, "task_status", "UNKNOWN")
                if status in {"SUCCEEDED", "FAILED", "CANCELED", "CANCELLED", "UNKNOWN"}:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    console.print("[red]❌ ASR 任务等待超时[/red]")
                    return None
                time.sleep(min(self.POLL_INTERVAL_SECONDS, remaining))

            if status != "SUCCEEDED":
                console.print(f"[red]❌ 转写任务结束，状态: {status}[/red]")
                return None
            results = self._field(output, "results", []) or []
            if not results:
                console.print("[red]❌ 没有转写结果[/red]")
                return None
            first = results[0]
            if self._field(first, "subtask_status") == "FAILED":
                console.print(
                    f"[red]❌ 转写任务失败: {self._field(first, 'message', '未知错误')}[/red]"
                )
                return None
            transcription_url = self._field(first, "transcription_url")
            if not transcription_url:
                console.print("[red]❌ 未找到 transcription_url[/red]")
                return None
            if urlsplit(transcription_url).scheme.lower() not in {"http", "https"}:
                console.print("[red]❌ 转写结果地址协议无效[/red]")
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                console.print("[red]❌ ASR 任务等待超时[/red]")
                return None
            response_timeout = min(float(self.request_timeout), remaining)
            with request.urlopen(transcription_url, timeout=response_timeout) as response:
                result_json = json.loads(response.read().decode("utf8"))
            transcripts = result_json.get("transcripts") or []
            if not transcripts:
                console.print("[yellow]⚠ 未检测到语音内容[/yellow]")
                return "（音频中未检测到语音内容）"
            text = transcripts[0].get("text", "")
            if not isinstance(text, str):
                return None
            text = text.strip()
            console.print(f"[green]✅ 语音识别完成（{len(text)} 字）[/green]")
            return text
        except Exception as exc:
            console.print(f"[red]❌ ASR 调用异常: {exc}[/red]")
            return None

    def transcribe_with_fallback(self, video_url: str, video_id: str, settings) -> Optional[str]:
        """Use direct cloud transcription, then an isolated OSS/FFmpeg fallback."""
        console.print("[cyan]🎯 方案1：直接视频 URL 转写[/cyan]")
        text = self.transcribe(video_url=video_url)
        if text:
            return text
        if not settings.oss_enable_fallback:
            console.print("[yellow]⚠ 兜底方案未启用（OSS_ENABLE_FALLBACK=false）[/yellow]")
            return None
        if not settings.validate_oss_config():
            console.print("[red]❌ OSS 配置不完整，无法启用兜底方案[/red]")
            return None

        from src.audio_processor import AudioProcessor
        from src.oss_client import OSSClient

        settings.temp_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix="douyin-asr-", dir=settings.temp_dir))
        oss_client = None
        oss_path = None
        try:
            request_timeout = settings.request_timeout
            processor = AudioProcessor(
                temp_dir=work_dir,
                cleanup=settings.cleanup_temp_files,
                timeout=request_timeout,
                download_timeout=settings.download_timeout,
                max_download_bytes=settings.max_download_bytes,
                ffmpeg_timeout=settings.ffmpeg_timeout,
            )
            temp_video = work_dir / "video.mp4"
            temp_audio = work_dir / "audio.wav"
            console.print("[cyan]🎯 方案2：OSS + FFmpeg 兜底[/cyan]")
            if not processor.download_video(video_url, temp_video):
                return None
            audio_path = processor.extract_audio(temp_video, output_path=temp_audio)
            if not audio_path:
                return None
            oss_client = OSSClient(
                access_key_id=settings.oss_access_key_id,
                access_key_secret=settings.oss_access_key_secret,
                bucket_name=settings.oss_bucket_name,
                endpoint=settings.oss_endpoint,
                endpoint_internal=settings.oss_endpoint_internal or None,
                cdn_domain=settings.oss_cdn_domain or None,
                request_timeout=request_timeout,
                sign_url_expires=max(3600, settings.asr_timeout + 300),
            )
            upload_result = oss_client.upload_audio(audio_path)
            if not upload_result:
                return None
            oss_url, oss_path = upload_result
            return self.transcribe(video_url=oss_url)
        except Exception as exc:
            console.print(f"[red]❌ 兜底方案异常: {exc}[/red]")
            return None
        finally:
            if oss_path and oss_client:
                try:
                    oss_client.delete_file(oss_path)
                except Exception as exc:
                    console.print(f"[yellow]⚠ 删除 OSS 文件失败: {exc}[/yellow]")
            if settings.cleanup_temp_files:
                try:
                    shutil.rmtree(work_dir)
                except OSError as exc:
                    console.print(f"[yellow]⚠ 删除临时目录失败: {exc}[/yellow]")

    def transcribe_with_timestamp(self, audio_path: Path) -> Optional[list]:
        """Timestamp support is not implemented."""
        console.print("[yellow]⚠ 带时间戳的转写功能尚未实现[/yellow]")
        return None
