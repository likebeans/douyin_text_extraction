"""配置管理模块"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """应用配置"""
    
    # 必需配置
    dashscope_api_key: str = "sk-0d96a068912c44ac8e661f3419672c9d"
    
    # 可选配置
    max_video_duration: int = 600  # 最大视频时长（秒）
    asr_model: str = "paraformer-v2"  # ASR 模型
    output_dir: Path = Path("./output")  # 输出目录
    
    # 请求配置
    request_timeout: int = 30  # HTTP 请求超时（秒）
    retry_times: int = 3  # 失败重试次数
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    def validate_config(self) -> bool:
        """验证配置是否完整"""
        if not self.dashscope_api_key or self.dashscope_api_key == "your_api_key_here":
            return False
        return True


# 全局配置实例
settings = Settings()
