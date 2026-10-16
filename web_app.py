#!/usr/bin/env python3
"""抖音视频文本提取工具的 Flask Web 应用。"""
from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import tempfile
from pathlib import Path
from threading import BoundedSemaphore, Lock
from typing import Any, get_args
from urllib.parse import urlsplit

from dotenv import dotenv_values, set_key
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import Settings

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

# Relative to the process working directory so deployments and tests can select their own .env.
ENV_FILE = Path(".env")
CONFIG_FIELDS = {
    "ASR_PROVIDER": "asr_provider",
    "DASHSCOPE_API_KEY": "dashscope_api_key",
    "MAX_VIDEO_DURATION": "max_video_duration",
    "ASR_MODEL": "asr_model",
    "WHISPER_MODEL": "whisper_model",
    "LOCAL_ASR_ENGINE": "local_asr_engine",
    "OUTPUT_DIR": "output_dir",
    "OSS_ENABLE_FALLBACK": "oss_enable_fallback",
    "OSS_ACCESS_KEY_ID": "oss_access_key_id",
    "OSS_ACCESS_KEY_SECRET": "oss_access_key_secret",
    "OSS_BUCKET_NAME": "oss_bucket_name",
    "OSS_ENDPOINT": "oss_endpoint",
}
SECRET_FIELDS = {"DASHSCOPE_API_KEY", "OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET"}
ENV_NAMES = {field: field for field in CONFIG_FIELDS}
ASR_MODELS = {"paraformer-v2"}
WHISPER_MODELS = set(get_args(Settings.model_fields["whisper_model"].annotation))
_env_write_lock = Lock()

from src.service import ExtractionError, ExtractionService

_extraction_slots = None
_slots_lock = Lock()


def load_settings() -> Settings:
    """Read current settings without mutating process environment."""
    return Settings(_env_file=ENV_FILE)


def extraction_slots(settings: Settings):
    global _extraction_slots
    with _slots_lock:
        if _extraction_slots is None:
            _extraction_slots = BoundedSemaphore(settings.web_max_concurrent_extractions)
        return _extraction_slots


def get_env_config() -> dict[str, str | None]:
    """Read .env without interpolation or modifying the process environment."""
    if not ENV_FILE.exists():
        return {}
    return dotenv_values(ENV_FILE, encoding="utf-8", interpolate=False)


def save_env_config(values: dict[str, str]) -> bool:
    """Atomically update known .env keys while preserving comments and unrelated lines."""
    temporary_path: Path | None = None
    try:
        if any(key not in CONFIG_FIELDS or any(char in value for char in "\r\n\x00") for key, value in values.items()):
            return False
        with _env_write_lock:
            ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{ENV_FILE.name}.", suffix=".tmp", dir=ENV_FILE.parent)
            temporary_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as target:
                if ENV_FILE.exists():
                    target.write(ENV_FILE.read_text(encoding="utf-8"))
                target.flush()
                os.fsync(target.fileno())
            os.chmod(temporary_path, 0o600)

            for key, value in values.items():
                set_key(temporary_path, key, value, quote_mode="always", export=False)

            with temporary_path.open("rb") as updated_file:
                os.fsync(updated_file.fileno())
            os.replace(temporary_path, ENV_FILE)
            temporary_path = None
            try:
                directory_fd = os.open(ENV_FILE.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
        return True
    except (OSError, UnicodeError, ValueError):
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _host_is_loopback(host_header: str | None) -> bool:
    if not host_header:
        return False
    try:
        hostname = urlsplit(f"//{host_header}").hostname
    except ValueError:
        return False
    if not hostname:
        return False
    if hostname.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _peer_is_loopback(address: str | None) -> bool:
    if not address:
        return False
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def _origin_is_same_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
        if parsed.username or parsed.password or not parsed.scheme or not parsed.hostname:
            return False
        request_host = urlsplit(f"//{request.host}")
        host = parsed.hostname.lower().rstrip(".")
        expected_host = (request_host.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() != request.scheme.lower() or host != expected_host:
            return False
        origin_port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        request_port = request_host.port or (443 if request.scheme.lower() == "https" else 80)
        return origin_port == request_port and parsed.path in ("", "/") and not parsed.query and not parsed.fragment
    except ValueError:
        return False


def _api_error(message: str, status: int):
    response = jsonify({"success": False, "error": message})
    if status == 401:
        response.headers["WWW-Authenticate"] = 'Bearer realm="douyin-api"'
    return response, status


@app.before_request
def protect_api_routes():
    if not request.path.startswith("/api/") or request.path == "/api/health":
        return None

    # Browser requests must be same-origin. Clients without Origin remain supported.
    fetch_site = request.headers.get("Sec-Fetch-Site", "").lower()
    if fetch_site and fetch_site != "same-origin":
        return _api_error("跨站请求不允许", 403)
    origin = request.headers.get("Origin")
    try:
        settings = load_settings()
    except Exception:
        return _api_error("服务配置无效", 500)
    public_origin_matches = (
        bool(settings.web_api_token)
        and bool(settings.web_public_origin)
        and origin == settings.web_public_origin
    )
    if origin and not (_origin_is_same_origin(origin) or public_origin_matches):
        return _api_error("跨站请求不允许", 403)

    if settings.web_api_token:
        provided = request.headers.get("X-API-Token", "")
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip()
            if not provided:
                provided = bearer
        try:
            authorized = bool(provided) and hmac.compare_digest(
                provided.encode("utf-8"), settings.web_api_token.encode("utf-8")
            )
        except UnicodeEncodeError:
            authorized = False
        if not authorized:
            return _api_error("需要有效的 API 令牌", 401)
        return None

    # No token is an intentional local-only mode. Proxy headers are not trusted.
    if not (_peer_is_loopback(request.remote_addr) and _host_is_loopback(request.host)):
        return _api_error("未配置 API 令牌时仅允许本机访问", 403)
    return None


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    if request.path.startswith("/api/"):
        message = "请求体过大" if isinstance(error, RequestEntityTooLarge) else error.description
        return _api_error(message, error.code or 500)
    return error


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    if isinstance(error, HTTPException):
        return handle_http_error(error)
    logger.error("Unhandled web request failure (%s)", type(error).__name__)
    if request.path.startswith("/api/"):
        return _api_error("服务器内部错误", 500)
    return "服务器内部错误", 500


def _json_object() -> dict[str, Any] | tuple[Any, int]:
    content_length = request.content_length
    if content_length is not None and content_length > app.config["MAX_CONTENT_LENGTH"]:
        return _api_error("请求体过大", 413)
    if not request.is_json:
        return _api_error("请求必须使用 JSON 格式", 415)
    try:
        data = request.get_json()
    except RequestEntityTooLarge:
        raise
    except (ValueError, HTTPException):
        return _api_error("JSON 格式无效", 400)
    if not isinstance(data, dict):
        return _api_error("JSON 请求体必须是对象", 400)
    return data


def _configured_fields(settings: Settings) -> dict[str, Any]:
    return {
        "ASR_PROVIDER": settings.asr_provider,
        "DASHSCOPE_API_KEY": "",
        "DASHSCOPE_API_KEY_CONFIGURED": bool(settings.dashscope_api_key),
        "MAX_VIDEO_DURATION": str(settings.max_video_duration),
        "ASR_MODEL": settings.asr_model,
        "WHISPER_MODEL": settings.whisper_model,
        "LOCAL_ASR_ENGINE": settings.local_asr_engine,
        "OUTPUT_DIR": str(settings.output_dir),
        "OSS_ENABLE_FALLBACK": str(settings.oss_enable_fallback).lower(),
        "OSS_ACCESS_KEY_ID_CONFIGURED": bool(settings.oss_access_key_id),
        "OSS_ACCESS_KEY_SECRET": "",
        "OSS_ACCESS_KEY_SECRET_CONFIGURED": bool(settings.oss_access_key_secret),
        "OSS_BUCKET_NAME": settings.oss_bucket_name,
        "OSS_ENDPOINT": settings.oss_endpoint,
        "ENVIRONMENT_FIELDS": [
            key for key in CONFIG_FIELDS
            if ENV_NAMES[key].lower() in {name.lower() for name in os.environ}
        ],
    }


def _parse_text_field(data: dict[str, Any], key: str, *, max_length: int = 4096) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} 必须是字符串")
    value = value.strip()
    if len(value) > max_length or any(char in value for char in "\r\n\x00"):
        raise ValueError(f"{key} 格式无效")
    return value


def _parse_config_update(data: dict[str, Any], current: Settings) -> dict[str, str]:
    unknown = set(data) - CONFIG_FIELDS.keys()
    if unknown:
        raise ValueError("包含不支持的配置项")

    updates: dict[str, str] = {}
    normalized: dict[str, Any] = {}
    for key in data:
        if key == "ASR_PROVIDER":
            value = _parse_text_field(data, key, max_length=32)
            if value not in {"dashscope", "local"}:
                raise ValueError("ASR 提供商无效")
            normalized[key] = value
        elif key == "ASR_MODEL":
            value = _parse_text_field(data, key, max_length=64)
            if value not in ASR_MODELS:
                raise ValueError("仅支持 paraformer-v2 文件识别模型")
            normalized[key] = value
        elif key == "LOCAL_ASR_ENGINE":
            value = _parse_text_field(data, key, max_length=32)
            if value not in {"whisper", "sensevoice"}:
                raise ValueError("本地识别引擎无效")
            normalized[key] = value
        elif key == "WHISPER_MODEL":
            value = _parse_text_field(data, key, max_length=32)
            if value not in WHISPER_MODELS:
                raise ValueError("Whisper 模型无效")
            normalized[key] = value
        elif key == "MAX_VIDEO_DURATION":
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                raise ValueError("MAX_VIDEO_DURATION 必须是 1 到 3600 的整数")
            try:
                duration = int(value)
            except (TypeError, ValueError):
                raise ValueError("MAX_VIDEO_DURATION 必须是 1 到 3600 的整数") from None
            if str(value).strip() != str(duration) or not 1 <= duration <= 3600:
                raise ValueError("MAX_VIDEO_DURATION 必须是 1 到 3600 的整数")
            normalized[key] = duration
        elif key == "OSS_ENABLE_FALLBACK":
            value = data[key]
            if isinstance(value, bool):
                normalized[key] = value
            elif isinstance(value, str) and value.strip().lower() in {"true", "false"}:
                normalized[key] = value.strip().lower() == "true"
            else:
                raise ValueError("OSS_ENABLE_FALLBACK 必须是布尔值")
        else:
            limit = 1024 if key == "OUTPUT_DIR" else 4096
            normalized[key] = _parse_text_field(data, key, max_length=limit)

    current_values: dict[str, Any] = {
        "ASR_PROVIDER": current.asr_provider,
        "DASHSCOPE_API_KEY": current.dashscope_api_key,
        "MAX_VIDEO_DURATION": current.max_video_duration,
        "ASR_MODEL": current.asr_model,
        "WHISPER_MODEL": current.whisper_model,
        "LOCAL_ASR_ENGINE": current.local_asr_engine,
        "OUTPUT_DIR": str(current.output_dir),
        "OSS_ENABLE_FALLBACK": current.oss_enable_fallback,
        "OSS_ACCESS_KEY_ID": current.oss_access_key_id,
        "OSS_ACCESS_KEY_SECRET": current.oss_access_key_secret,
        "OSS_BUCKET_NAME": current.oss_bucket_name,
        "OSS_ENDPOINT": current.oss_endpoint,
    }

    effective_values = current_values.copy()
    # Empty ordinary fields from the UI mean “leave as is” too; there is no clear action for secrets.
    for key, value in normalized.items():
        if key != "OUTPUT_DIR" and key not in SECRET_FIELDS and isinstance(value, str) and not value:
            normalized[key] = current_values[key]
    environment_names = {name.upper() for name in os.environ}
    for key, value in normalized.items():
        # Empty secret inputs mean “keep the existing value”, independent of provider toggles.
        if key in SECRET_FIELDS and not value:
            continue
        if ENV_NAMES[key].upper() in environment_names and value != current_values[key]:
            raise ValueError(f"{key} 已由环境变量设置，不能通过页面修改")
        effective_values[key] = value
        if value != current_values[key]:
            updates[key] = str(value).lower() if isinstance(value, bool) else str(value)

    provider = effective_values["ASR_PROVIDER"]
    if provider == "dashscope" and not effective_values["DASHSCOPE_API_KEY"]:
        raise ValueError("使用 DashScope 时必须先配置 API Key")
    if effective_values["OSS_ENABLE_FALLBACK"]:
        if not all(effective_values[field] for field in (
            "OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_BUCKET_NAME", "OSS_ENDPOINT"
        )):
            raise ValueError("启用 OSS 兜底方案时需要填写完整的 OSS 配置")

    # Validate the complete candidate through Settings before writing it.
    candidate = current.model_dump()
    for key, value in effective_values.items():
        candidate[CONFIG_FIELDS[key]] = value
    candidate_settings = Settings(_env_file=None, **candidate)
    if candidate_settings.asr_provider == "dashscope" and not candidate_settings.validate_config():
        raise ValueError("使用 DashScope 时必须先配置 API Key")
    if not candidate_settings.validate_oss_config():
        raise ValueError("启用 OSS 兜底方案时需要填写完整的 OSS 配置")
    return updates


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/config")
def config_page():
    # Runtime configuration is fetched only through the authenticated API.
    return render_template("config.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    try:
        settings = load_settings()
    except Exception:
        return _api_error("服务配置无效", 500)
    if not settings.web_config_enabled:
        return _api_error("配置页面已禁用", 404)
    return jsonify({"success": True, "config": _configured_fields(settings)})


@app.route("/api/config", methods=["POST"])
def save_config():
    try:
        current = load_settings()
    except Exception:
        return _api_error("服务配置无效", 500)
    if not current.web_config_enabled:
        return _api_error("配置页面已禁用", 404)

    parsed = _json_object()
    if isinstance(parsed, tuple):
        return parsed
    try:
        updates = _parse_config_update(parsed, current)
    except ValueError as error:
        return _api_error(str(error), 400)

    if not updates:
        return jsonify({"success": True, "message": "配置未发生变化"})
    if not save_env_config(updates):
        return _api_error("配置保存失败", 500)
    return jsonify({"success": True, "message": "配置保存成功"})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


@app.route("/api/extract", methods=["POST"])
def extract_video():
    parsed = _json_object()
    if isinstance(parsed, tuple):
        return parsed
    link = parsed.get("link")
    if not isinstance(link, str) or not link.strip() or len(link) > 8192 or "\x00" in link:
        return _api_error("请提供有效的抖音链接", 400)

    try:
        current_settings = load_settings()
    except Exception:
        return _api_error("服务配置无效", 500)
    if not current_settings.validate_config():
        return _api_error("ASR 配置无效，请检查配置页面", 400)
    slots = extraction_slots(current_settings)
    if not slots.acquire(blocking=False):
        return _api_error("当前提取任务较多，请稍后重试", 429)

    try:
        result = ExtractionService(current_settings).extract(link.strip())
        return jsonify(result.to_dict())
    except ExtractionError as error:
        status = getattr(error, "status_code", 400)
        if not isinstance(status, int) or not 400 <= status <= 599:
            status = 400
        message = str(error).strip()
        if not message or len(message) > 500:
            message = "视频文本提取失败"
        return _api_error(message, status)
    except Exception as error:
        logger.error("Unexpected extraction failure (%s)", type(error).__name__)
        return _api_error("服务器内部错误", 500)
    finally:
        slots.release()


def get_local_ip() -> str:
    """Return a local address for the startup banner when available."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


if __name__ == "__main__":
    from run_web import main

    main()
