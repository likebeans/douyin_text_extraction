"""配置管理：环境变量优先于 .env，读取配置不修改进程环境。"""
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MAX_VIDEO_DURATION = 600
DEFAULT_ASR_MODEL = "paraformer-v2"
DEFAULT_ASR_PROVIDER = "dashscope"
DEFAULT_OUTPUT_DIR = "./output"
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_RETRY_TIMES = 3

ASR_PROVIDER_DASHSCOPE = "dashscope"
ASR_PROVIDER_LOCAL = "local"


class Settings(BaseSettings):
    """配置优先级：显式参数 > 环境变量 > .env > 默认值。"""

    dashscope_api_key: str = Field(default="", repr=False)
    asr_provider: Literal["dashscope", "local"] = DEFAULT_ASR_PROVIDER
    asr_model: str = Field(default=DEFAULT_ASR_MODEL, min_length=1)
    whisper_model: Literal["tiny", "base", "small", "medium", "large", "turbo"] = "base"
    max_video_duration: int = Field(default=DEFAULT_MAX_VIDEO_DURATION, gt=0)
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)

    request_timeout: int = Field(default=DEFAULT_REQUEST_TIMEOUT, gt=0)
    download_timeout: int = Field(default=300, gt=0)
    retry_times: int = Field(default=DEFAULT_RETRY_TIMES, ge=0, le=10)
    asr_timeout: int = Field(default=600, gt=0)
    ffmpeg_timeout: int = Field(default=120, gt=0)
    max_download_bytes: int = Field(default=512 * 1024 * 1024, gt=0)

    oss_access_key_id: str = Field(default="", repr=False)
    oss_access_key_secret: str = Field(default="", repr=False)
    oss_bucket_name: str = ""
    oss_endpoint: str = ""
    oss_endpoint_internal: str = ""
    oss_region: str = ""
    oss_cdn_domain: str = ""
    oss_enable_fallback: bool = False

    temp_dir: Path = Path("./temp")
    cleanup_temp_files: bool = True

    flask_host: str = "127.0.0.1"
    flask_port: int = Field(default=5000, ge=1, le=65535)
    flask_debug: bool = False
    web_api_token: str = Field(default="", repr=False)
    web_config_enabled: bool = True
    web_public_origin: str = ""  # HTTPS 反向代理的外部 Origin，例如 https://tool.example.com
    web_max_concurrent_extractions: int = Field(default=2, ge=1, le=32)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("web_public_origin")
    @classmethod
    def validate_public_origin(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            return ""
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or (parsed.port is not None and not 1 <= parsed.port <= 65535)
            or any(char.isspace() for char in value)
            or "\\" in value
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("WEB_PUBLIC_ORIGIN 必须是包含协议和主机的完整 Origin")
        return value

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        def literal_dotenv():
            # Web 写入的密钥和路径必须按字面量读取，不能再次展开 ${...}。
            files = dotenv_settings.env_file
            if files is None:
                return {}
            if isinstance(files, (str, Path)):
                files = [files]
            values = {}
            for path in files:
                values.update({
                    key.lower(): value
                    for key, value in dotenv_values(path, encoding="utf-8", interpolate=False).items()
                    if value is not None
                })
            return values

        return init_settings, env_settings, literal_dotenv, file_secret_settings

    def validate_config(self) -> bool:
        """本地依赖在使用时检查；云端需要非空 API Key。"""
        return self.asr_provider == ASR_PROVIDER_LOCAL or bool(self.dashscope_api_key.strip())

    def validate_oss_config(self) -> bool:
        """仅在启用兜底方案时要求 OSS 配置完整。"""
        return not self.oss_enable_fallback or all(
            value.strip()
            for value in (
                self.oss_access_key_id,
                self.oss_access_key_secret,
                self.oss_bucket_name,
                self.oss_endpoint,
            )
        )
