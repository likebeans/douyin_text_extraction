"""配置不接受无效范围，密钥不出现在 repr 中。"""
import pytest
from pydantic import ValidationError

from config import Settings


@pytest.mark.parametrize("values", [
    {"asr_provider": "unknown"},
    {"request_timeout": 0},
    {"download_timeout": 0},
    {"asr_timeout": -1},
    {"ffmpeg_timeout": 0},
    {"max_video_duration": 0},
    {"max_download_bytes": 0},
    {"retry_times": -1},
    {"retry_times": 11},
    {"flask_port": 65536},
    {"web_max_concurrent_extractions": 0},
    {"whisper_model": "unknown"},
])
def test_invalid_config_rejected(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_secrets_hidden_from_repr():
    settings = Settings(_env_file=None, dashscope_api_key="dash-secret", oss_access_key_id="oss-id-secret", oss_access_key_secret="oss-secret", web_api_token="web-secret")
    assert all(secret not in repr(settings) for secret in ("dash-secret", "oss-id-secret", "oss-secret", "web-secret"))


def test_environment_overrides_env_file_without_mutation(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MAX_VIDEO_DURATION=120\nDASHSCOPE_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("MAX_VIDEO_DURATION", "60")
    assert Settings(_env_file=env_file).max_video_duration == 60
    env_file.write_text("MAX_VIDEO_DURATION=180\nDASHSCOPE_API_KEY=new-key\n", encoding="utf-8")
    monkeypatch.delenv("MAX_VIDEO_DURATION")
    assert Settings(_env_file=env_file).max_video_duration == 180
    assert Settings(_env_file=env_file).dashscope_api_key == "new-key"


def test_env_file_values_are_literal(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setenv("EXAMPLE_VALUE", "expanded")
    env_file.write_text("DASHSCOPE_API_KEY='literal-${EXAMPLE_VALUE}-#value'\n", encoding="utf-8")
    assert Settings(_env_file=env_file).dashscope_api_key == "literal-${EXAMPLE_VALUE}-#value"


def test_default_web_is_local_and_debug_disabled():
    settings = Settings(_env_file=None)
    assert settings.flask_host == "127.0.0.1"
    assert settings.flask_debug is False


@pytest.mark.parametrize("origin", [
    "tool.example", "ftp://tool.example", "https://user:secret@tool.example",
    "https://tool.example/path", "https://tool.example?query=1",
    "https://tool.example#fragment", "https://tool.example:invalid",
    "https://tool.example:70000", "https://tool.example:0",
    "https://tool. example", "https://tool.example\n.invalid",
])
def test_invalid_public_origin_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, web_public_origin=origin)


def test_public_origin_accepts_external_https_and_strips_trailing_slash():
    settings = Settings(_env_file=None, web_public_origin=" https://tool.example:8443/ ")
    assert settings.web_public_origin == "https://tool.example:8443"
