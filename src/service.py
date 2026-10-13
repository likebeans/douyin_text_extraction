"""CLI 和 Web 共用的视频文本提取流程。"""
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from config import ASR_PROVIDER_DASHSCOPE, Settings
from src.asr_client import ASRClient
from src.audio_processor import AudioProcessor
from src.fetcher import DouyinFetcher, VideoMetadata
from src.local_asr_client import LocalASRClient
from src.parser import DouyinLinkParser


class ExtractionError(Exception):
    """可直接向使用者展示的提取错误，不包含服务端凭据。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ExtractionResult:
    metadata: VideoMetadata
    text: str

    def to_dict(self) -> dict:
        metadata = self.metadata.model_dump()
        metadata["douyin_url"] = f"https://www.douyin.com/video/{self.metadata.video_id}"
        return {"success": True, "metadata": metadata, "text": self.text}


class ExtractionService:
    """每次提取拥有独立网络会话和临时目录。"""

    def __init__(self, settings: Settings):
        self.settings = settings

    def extract(self, link: str) -> ExtractionResult:
        if not isinstance(link, str) or not link.strip():
            raise ExtractionError("请提供抖音链接")
        if len(link) > 8192:
            raise ExtractionError("链接或分享文本过长（最多 8192 个字符）")
        if not self.settings.validate_config():
            raise ExtractionError("未设置 DASHSCOPE_API_KEY，请先配置云端 API Key")

        local_asr = None
        processor = None
        if self.settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
            if not self.settings.validate_oss_config():
                raise ExtractionError("已启用 OSS 兜底，但 OSS 配置不完整")
        else:
            try:
                local_asr = LocalASRClient(model=self.settings.whisper_model)
            except ImportError as exc:
                raise ExtractionError("本地 Whisper 未安装，请运行 uv sync --extra local") from exc
            processor = AudioProcessor(
                temp_dir=self.settings.temp_dir,
                cleanup=self.settings.cleanup_temp_files,
                timeout=self.settings.request_timeout,
                max_download_bytes=self.settings.max_download_bytes,
                ffmpeg_timeout=self.settings.ffmpeg_timeout,
            )
            if not processor.check_ffmpeg():
                raise ExtractionError("FFmpeg 未安装，请安装后再使用本地转写")

        parser = DouyinLinkParser(
            timeout=self.settings.request_timeout,
            retry_times=self.settings.retry_times,
        )
        fetcher = DouyinFetcher(
            timeout=self.settings.request_timeout,
            retry_times=self.settings.retry_times,
        )
        try:
            video_id = parser.parse(link.strip())
            if not video_id:
                raise ExtractionError("链接解析失败，请检查链接是否有效且属于抖音")
            metadata = fetcher.fetch(video_id)
            if not metadata:
                raise ExtractionError("视频信息获取失败，视频可能不可访问或平台页面已变化", 502)
        finally:
            parser.close()
            fetcher.close()

        if metadata.duration > self.settings.max_video_duration:
            raise ExtractionError(
                f"视频时长（{metadata.duration}秒）超过限制（{self.settings.max_video_duration}秒）"
            )

        if self.settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
            client = ASRClient(
                self.settings.dashscope_api_key,
                self.settings.asr_model,
                request_timeout=self.settings.request_timeout,
                asr_timeout=self.settings.asr_timeout,
            )
            text = client.transcribe_with_fallback(
                video_url=metadata.video_url,
                video_id=video_id,
                settings=self.settings,
            )
        else:
            text = self._transcribe_local(metadata, processor, local_asr)

        if not text or not text.strip():
            raise ExtractionError("语音识别未返回文本，请检查音轨、服务配置及服务端日志", 502)
        return ExtractionResult(metadata, text.strip())

    def _transcribe_local(self, metadata, processor, local_asr):
        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix="douyin-", dir=self.settings.temp_dir))
        try:
            video_path = processor.download_video(metadata.video_url, work_dir / "video.mp4")
            if not video_path:
                raise ExtractionError("视频下载失败，请检查网络或下载大小限制", 502)
            audio_path = processor.extract_audio(video_path, output_path=work_dir / "audio.wav")
            if not audio_path:
                raise ExtractionError("音频提取失败，请检查视频是否包含可用音轨", 502)
            return local_asr.transcribe(audio_path=audio_path)
        finally:
            if self.settings.cleanup_temp_files:
                try:
                    shutil.rmtree(work_dir)
                except OSError:
                    logging.getLogger(__name__).warning("临时目录清理失败，请检查 TEMP_DIR 下的残留文件")
