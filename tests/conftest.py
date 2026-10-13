"""Keep the ordinary test suite isolated from developer credentials and networks."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest
import requests
import urllib.request
from dotenv import dotenv_values


# Capture opt-in integration credentials in memory, then remove them from the
# environment before application modules (and Settings singletons) are imported.
_OSS_KEYS = (
    "OSS_ACCESS_KEY_ID",
    "OSS_ACCESS_KEY_SECRET",
    "OSS_BUCKET_NAME",
    "OSS_ENDPOINT",
    "OSS_ENDPOINT_INTERNAL",
    "OSS_CDN_DOMAIN",
)
_PROJECT_ENV = Path(__file__).resolve().parents[1] / ".env"
_FILE_OSS_ENV = (
    dotenv_values(_PROJECT_ENV, encoding="utf-8", interpolate=False)
    if "--run-integration" in sys.argv and _PROJECT_ENV.is_file()
    else {}
)
_INTEGRATION_OSS_ENV = {
    key: os.environ.get(key) or _FILE_OSS_ENV.get(key) or ""
    for key in _OSS_KEYS
}

_ENV_KEYS = {
    "DASHSCOPE_API_KEY",
    "ASR_PROVIDER",
    "ASR_MODEL",
    "WHISPER_MODEL",
    "MAX_VIDEO_DURATION",
    "OUTPUT_DIR",
    "REQUEST_TIMEOUT",
    "RETRY_TIMES",
    "ASR_TIMEOUT",
    "FFMPEG_TIMEOUT",
    "MAX_DOWNLOAD_BYTES",
    "OSS_ENABLE_FALLBACK",
    "OSS_ACCESS_KEY_ID",
    "OSS_ACCESS_KEY_SECRET",
    "OSS_BUCKET_NAME",
    "OSS_ENDPOINT",
    "OSS_ENDPOINT_INTERNAL",
    "OSS_REGION",
    "OSS_CDN_DOMAIN",
    "TEMP_DIR",
    "CLEANUP_TEMP_FILES",
    "FLASK_HOST",
    "FLASK_PORT",
    "FLASK_DEBUG",
    "WEB_API_TOKEN",
    "WEB_CONFIG_ENABLED",
    "WEB_PUBLIC_ORIGIN",
    "WEB_MAX_CONCURRENT_EXTRACTIONS",
}
for _key in _ENV_KEYS:
    os.environ.pop(_key, None)

@pytest.fixture(autouse=True)
def isolated_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run tests that make real requests to external services",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: may call a real external service")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="requires explicit --run-integration opt-in")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def integration_oss_env(pytestconfig, monkeypatch):
    if not pytestconfig.getoption("--run-integration"):
        pytest.skip("requires explicit --run-integration opt-in")
    required = ("OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_BUCKET_NAME", "OSS_ENDPOINT")
    missing = [key for key in required if not _INTEGRATION_OSS_ENV.get(key, "").strip()]
    if missing:
        pytest.skip("OSS integration credentials are incomplete")
    for key, value in _INTEGRATION_OSS_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("OSS_ENABLE_FALLBACK", "false")
    return dict(_INTEGRATION_OSS_ENV)


@pytest.fixture(autouse=True)
def block_network(monkeypatch, request, pytestconfig):
    if pytestconfig.getoption("--run-integration") and "integration" in request.node.keywords:
        return

    def denied(*args, **kwargs):
        raise AssertionError("network access is disabled in the default test suite")

    monkeypatch.setattr(requests.sessions.Session, "request", denied)
    monkeypatch.setattr(urllib.request, "urlopen", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
