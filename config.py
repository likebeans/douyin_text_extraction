"""配置管理模块 - 所有配置项从环境变量读取"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# 默认常量配置
DEFAULT_MAX_VIDEO_DURATION = 600  # 默认最大视频时长（秒）
DEFAULT_ASR_MODEL = "paraformer-v2"  # 默认 Paraformer 模型
DEFAULT_ASR_PROVIDER = "dashscope"  # 默认 ASR 提供商：dashscope 或 local
DEFAULT_OUTPUT_DIR = "./output"  # 默认输出目录
DEFAULT_REQUEST_TIMEOUT = 30  # 默认 HTTP 请求超时（秒）
DEFAULT_RETRY_TIMES = 3  # 默认失败重试次数

# ASR 提供商选项
ASR_PROVIDER_DASHSCOPE = "dashscope"  # 阿里云 DashScope（云端）
ASR_PROVIDER_LOCAL = "local"  # 本地 Whisper（需要 GPU 或 CPU）


class Settings(BaseSettings):
    """应用配置 - 从 .env 文件或环境变量读取
    
    配置优先级：
    1. 环境变量
    2. .env 文件
    3. 默认值
    """
    
    # ============ 必需配置 ============
    dashscope_api_key: str = ""  # DashScope API Key（必需）
    
    # ============ ASR 配置 ============
    asr_provider: str = DEFAULT_ASR_PROVIDER  # ASR 提供商：dashscope（云端）或 local（本地）
    asr_model: str = DEFAULT_ASR_MODEL  # ASR 模型名称（DashScope 使用）
    max_video_duration: int = DEFAULT_MAX_VIDEO_DURATION  # 最大视频时长（秒）
    
    # ============ 输出配置 ============
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)  # 输出目录
    
    # ============ 请求配置 ============
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT  # HTTP 请求超时（秒）
    retry_times: int = DEFAULT_RETRY_TIMES  # 失败重试次数
    
    # ============ OSS 配置（兜底方案，可选）============
    oss_access_key_id: str = ""  # 阿里云 OSS AccessKey ID
    oss_access_key_secret: str = ""  # 阿里云 OSS AccessKey Secret
    oss_bucket_name: str = ""  # OSS Bucket 名称
    oss_endpoint: str = ""  # OSS Endpoint
    oss_enable_fallback: bool = False  # 是否启用 OSS 兜底方案
    
    # ============ 临时文件配置 ============
    temp_dir: Path = Path("./temp")  # 临时文件目录
    cleanup_temp_files: bool = True  # 是否自动清理临时文件
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略额外的环境变量
    )
    
    def validate_config(self) -> bool:
        """验证必需配置是否完整"""
        # 如果使用 DashScope，需要 API Key
        if self.asr_provider == ASR_PROVIDER_DASHSCOPE:
            if not self.dashscope_api_key:
                return False
        # 如果使用本地，需要检查 Whisper 是否可用（在运行时检查）
        return True
    
    def validate_oss_config(self) -> bool:
        """验证 OSS 配置是否完整"""
        if not self.oss_enable_fallback:
            return True  # 未启用兜底方案，不需要验证
        
        required_fields = [
            self.oss_access_key_id,
            self.oss_access_key_secret,
            self.oss_bucket_name,
            self.oss_endpoint,
        ]
        return all(required_fields)


# 全局配置实例
settings = Settings()
