"""Offline tests for the Web API, configuration boundary and browser routes."""
from __future__ import annotations

from threading import BoundedSemaphore

import pytest

import web_app
from config import Settings
from src.service import ExtractionError


CONFIG_ENV_NAMES = (
    "ASR_PROVIDER",
    "DASHSCOPE_API_KEY",
    "MAX_VIDEO_DURATION",
    "ASR_MODEL",
    "OUTPUT_DIR",
    "OSS_ENABLE_FALLBACK",
    "OSS_ACCESS_KEY_ID",
    "OSS_ACCESS_KEY_SECRET",
    "OSS_BUCKET_NAME",
    "OSS_ENDPOINT",
    "WEB_API_TOKEN",
    "WEB_CONFIG_ENABLED",
    "WEB_PUBLIC_ORIGIN",
    "WEB_MAX_CONCURRENT_EXTRACTIONS",
    "FLASK_HOST",
    "FLASK_PORT",
    "FLASK_DEBUG",
)


@pytest.fixture

def client(tmp_path, monkeypatch):
    for name in CONFIG_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ASR_PROVIDER=local\n", encoding="utf-8")
    monkeypatch.setattr(web_app, "ENV_FILE", env_file)
    web_app.app.config.update(TESTING=True, MAX_CONTENT_LENGTH=64 * 1024)
    web_app._extraction_slots = BoundedSemaphore(2)
    with web_app.app.test_client() as test_client:
        yield test_client


def token_headers(token="test-web-token"):
    return {"X-API-Token": token}


def post_config(client, data, headers=None):
    return client.post("/api/config", json=data, headers=headers or {})


def test_health_is_public_and_config_page_has_no_runtime_settings(client, monkeypatch):
    monkeypatch.setenv("WEB_API_TOKEN", "do-not-render-this-token")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "do-not-render-this-key")
    assert client.get("/api/health").status_code == 200
    page = client.get("/config")
    assert page.status_code == 200
    assert b"do-not-render-this-token" not in page.data
    assert b"do-not-render-this-key" not in page.data


def test_api_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setenv("WEB_API_TOKEN", "test-web-token")
    unauthenticated = client.get("/api/config")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["WWW-Authenticate"].startswith("Bearer ")
    assert client.get("/api/config", headers=token_headers()).status_code == 200
    assert client.get("/api/config", headers={"Authorization": "Bearer test-web-token"}).status_code == 200


def test_missing_token_mode_requires_loopback_peer_and_host(client):
    remote_peer = client.get(
        "/api/config",
        environ_base={"REMOTE_ADDR": "192.0.2.20"},
        headers={"Host": "localhost", "X-Forwarded-For": "127.0.0.1"},
    )
    assert remote_peer.status_code == 403

    remote_host = client.get(
        "/api/config",
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
        headers={"Host": "public.example", "X-Forwarded-Host": "localhost"},
    )
    assert remote_host.status_code == 403

    assert client.get("/api/config", headers={"Host": "127.0.0.1"}).status_code == 200


def test_cross_origin_and_fetch_site_are_rejected_even_with_token(client, monkeypatch):
    monkeypatch.setenv("WEB_API_TOKEN", "test-web-token")
    assert client.get(
        "/api/config",
        headers=token_headers() | {"Origin": "https://attacker.example"},
    ).status_code == 403
    assert client.get(
        "/api/config",
        headers=token_headers() | {"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.get(
        "/api/config",
        headers=token_headers() | {"Origin": "http://localhost"},
    ).status_code == 200


def test_https_reverse_proxy_origin_requires_exact_config_and_valid_token(client, monkeypatch):
    monkeypatch.setenv("WEB_API_TOKEN", "test-web-token")
    proxy_headers = token_headers() | {
        "Host": "tool.example",
        "Origin": "https://tool.example",
        "Sec-Fetch-Site": "same-origin",
        "X-Forwarded-Proto": "https",
    }
    assert client.get("/api/config", headers=proxy_headers).status_code == 403

    monkeypatch.setenv("WEB_PUBLIC_ORIGIN", "https://tool.example")
    assert client.get("/api/config", headers=proxy_headers).status_code == 200
    assert client.get(
        "/api/config", headers=proxy_headers | {"X-API-Token": "wrong-token"},
    ).status_code == 401
    for origin in ("https://tool.example.attacker.example", "https://tool.example:8443", "http://other.example"):
        assert client.get(
            "/api/config", headers=proxy_headers | {"Origin": origin},
        ).status_code == 403
    assert client.get(
        "/api/config", headers=proxy_headers | {"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403


def test_public_origin_does_not_allow_remote_access_without_token(client, monkeypatch):
    monkeypatch.setenv("WEB_PUBLIC_ORIGIN", "https://tool.example")
    assert client.get(
        "/api/config", headers={"Origin": "https://tool.example"},
    ).status_code == 403
    assert client.get(
        "/api/config", base_url="https://tool.example", headers={"Origin": "https://tool.example"},
    ).status_code == 403


def test_disabled_config_endpoints_are_not_found_but_page_is_safe(client, monkeypatch):
    monkeypatch.setenv("WEB_CONFIG_ENABLED", "false")
    assert client.get("/config").status_code == 200
    assert client.get("/api/config").status_code == 404
    assert post_config(client, {"ASR_PROVIDER": "local"}).status_code == 404


@pytest.mark.parametrize(
    ("body", "expected_status"),
    [
        (b"[]", 400),
        (b"null", 400),
        (b"{broken", 400),
    ],
)
def test_config_rejects_non_object_or_invalid_json(client, body, expected_status):
    response = client.post("/api/config", data=body, content_type="application/json")
    assert response.status_code == expected_status
    assert response.is_json


def test_config_rejects_non_json_content_type(client):
    response = client.post("/api/config", data="ASR_PROVIDER=local")
    assert response.status_code == 415
    assert response.is_json


def test_config_rejects_unknown_fields_invalid_types_and_realtime_models(client):
    for data in (
        {"SECRET_EXTRA_FIELD": "never-echo-this"},
        {"ASR_PROVIDER": ["local"]},
        {"MAX_VIDEO_DURATION": True},
        {"MAX_VIDEO_DURATION": "3601"},
        {"ASR_MODEL": "paraformer-realtime-v2"},
        {"OUTPUT_DIR": "safe\nDASHSCOPE_API_KEY=injected"},
    ):
        response = post_config(client, data)
        assert response.status_code == 400
        assert response.is_json
        assert "never-echo-this" not in response.get_data(as_text=True)
        assert "injected" not in response.get_data(as_text=True)


def test_config_update_is_atomic_quoted_and_preserves_comments_without_leaking_secrets(client):
    env_file = web_app.ENV_FILE
    env_file.write_text(
        "# Keep this note\nASR_PROVIDER=local\nOSS_ACCESS_KEY_ID=old-id\n"
        "OSS_ACCESS_KEY_SECRET=old-secret\nDASHSCOPE_API_KEY=old-dash-key\n",
        encoding="utf-8",
    )
    new_secret = "sk-test-${HOME} 'literal' # secret"
    new_oss_secret = "oss-${PATH} 'quoted' # literal"
    response = post_config(
        client,
        {
            "ASR_PROVIDER": "dashscope",
            "DASHSCOPE_API_KEY": new_secret,
            "OSS_ACCESS_KEY_SECRET": new_oss_secret,
            "MAX_VIDEO_DURATION": "180",
            "ASR_MODEL": "paraformer-v2",
        },
    )
    assert response.status_code == 200
    raw_env = env_file.read_text(encoding="utf-8")
    assert "# Keep this note" in raw_env
    assert "OSS_ACCESS_KEY_ID=old-id" in raw_env
    saved_values = web_app.get_env_config()
    assert saved_values["DASHSCOPE_API_KEY"] == new_secret
    assert saved_values["OSS_ACCESS_KEY_SECRET"] == new_oss_secret
    loaded_settings = web_app.load_settings()
    assert loaded_settings.dashscope_api_key == new_secret
    assert loaded_settings.oss_access_key_secret == new_oss_secret

    result = client.get("/api/config").get_json()["config"]
    assert result["DASHSCOPE_API_KEY"] == ""
    assert result["DASHSCOPE_API_KEY_CONFIGURED"] is True
    assert result["OSS_ACCESS_KEY_ID_CONFIGURED"] is True
    assert result["OSS_ACCESS_KEY_SECRET"] == ""
    assert result["OSS_ACCESS_KEY_SECRET_CONFIGURED"] is True
    for secret in (new_secret, new_oss_secret, "old-id", "old-secret"):
        assert secret not in str(result)
    assert "\\${HOME}" not in raw_env
    assert "\\${PATH}" not in raw_env


def test_empty_secret_inputs_and_disabled_fallback_preserve_all_credentials(client):
    env_file = web_app.ENV_FILE
    env_file.write_text(
        "ASR_PROVIDER=local\nDASHSCOPE_API_KEY=dash-old\nOSS_ACCESS_KEY_ID=oss-id-old\n"
        "OSS_ACCESS_KEY_SECRET=oss-secret-old\nOSS_BUCKET_NAME=existing-bucket\nOSS_ENDPOINT=endpoint.example\n",
        encoding="utf-8",
    )
    response = post_config(
        client,
        {
            "ASR_PROVIDER": "local",
            "DASHSCOPE_API_KEY": "",
            "MAX_VIDEO_DURATION": 300,
            "OSS_ENABLE_FALLBACK": False,
            "OSS_ACCESS_KEY_ID": "",
            "OSS_ACCESS_KEY_SECRET": "",
            "OSS_BUCKET_NAME": "",
            "OSS_ENDPOINT": "",
        },
    )
    assert response.status_code == 200
    settings = web_app.load_settings()
    assert settings.dashscope_api_key == "dash-old"
    assert settings.oss_access_key_id == "oss-id-old"
    assert settings.oss_access_key_secret == "oss-secret-old"
    assert settings.oss_bucket_name == "existing-bucket"
    assert settings.oss_endpoint == "endpoint.example"


def test_environment_values_win_and_conflicting_updates_are_rejected(client, monkeypatch):
    monkeypatch.setenv("MAX_VIDEO_DURATION", "123")
    assert web_app.load_settings().max_video_duration == 123
    response = client.get("/api/config")
    assert response.get_json()["config"]["MAX_VIDEO_DURATION"] == "123"
    assert "MAX_VIDEO_DURATION" in response.get_json()["config"]["ENVIRONMENT_FIELDS"]

    update = post_config(client, {"MAX_VIDEO_DURATION": 124})
    assert update.status_code == 400
    assert "124" not in update.get_data(as_text=True)
    assert "MAX_VIDEO_DURATION=123" not in web_app.ENV_FILE.read_text(encoding="utf-8")


def test_secret_values_are_not_reflected_in_validation_errors(client):
    secret = "sk-do-not-reflect-this"
    response = post_config(client, {"ASR_PROVIDER": secret})
    assert response.status_code == 400
    assert secret not in response.get_data(as_text=True)


def test_extract_validates_payload_before_service(client, monkeypatch):
    service = pytest.MonkeyPatch()
    service.setattr(web_app, "ExtractionService", object)
    for body in ([], {"link": 1}, {"link": ""}, {"link": "x" * 8193}, {"link": "bad\x00link"}):
        response = client.post("/api/extract", json=body)
        assert response.status_code == 400
    service.undo()


def test_extract_preserves_newlines_in_share_text(client, monkeypatch):
    received = {}

    class Result:
        def to_dict(self):
            return {"success": True, "metadata": {}, "text": "ok"}

    class Service:
        def __init__(self, settings):
            pass

        def extract(self, link):
            received["link"] = link
            return Result()

    monkeypatch.setattr(web_app, "ExtractionService", Service)
    share_text = "复制这段内容，打开抖音\n搜索视频内容"
    response = client.post("/api/extract", json={"link": share_text})
    assert response.status_code == 200
    assert received["link"] == share_text


def test_extract_forwards_link_returns_result_and_always_releases_slot(client, monkeypatch):
    class Result:
        def to_dict(self):
            return {"success": True, "metadata": {"douyin_url": "https://www.douyin.com/video/1"}, "text": "hello"}

    class Service:
        def __init__(self, settings):
            assert isinstance(settings, Settings)

        def extract(self, link):
            assert link == "https://v.douyin.com/short/"
            return Result()

    monkeypatch.setattr(web_app, "ExtractionService", Service)
    response = client.post("/api/extract", json={"link": " https://v.douyin.com/short/ "})
    assert response.status_code == 200
    assert response.get_json()["text"] == "hello"
    assert web_app._extraction_slots.acquire(blocking=False)
    web_app._extraction_slots.release()


def test_extract_service_errors_and_unexpected_errors_do_not_leak_internal_details(client, monkeypatch):
    class Service:
        def __init__(self, settings):
            pass

        def extract(self, link):
            raise RuntimeError("internal secret traceback marker")

    monkeypatch.setattr(web_app, "ExtractionService", Service)
    response = client.post("/api/extract", json={"link": "https://v.douyin.com/short/"})
    assert response.status_code == 500
    assert "internal secret traceback marker" not in response.get_data(as_text=True)

    class ExpectedService(Service):
        def extract(self, link):
            raise ExtractionError("video is unavailable", 502)

    monkeypatch.setattr(web_app, "ExtractionService", ExpectedService)
    response = client.post("/api/extract", json={"link": "https://v.douyin.com/short/"})
    assert response.status_code == 502
    assert response.get_json()["error"] == "video is unavailable"


def test_extract_concurrency_limit_is_non_blocking_and_slot_is_released_on_error(client, monkeypatch):
    class Service:
        def __init__(self, settings):
            pass

        def extract(self, link):
            raise RuntimeError("boom")

    monkeypatch.setattr(web_app, "ExtractionService", Service)
    web_app._extraction_slots = BoundedSemaphore(1)
    assert web_app._extraction_slots.acquire(blocking=False)
    response = client.post("/api/extract", json={"link": "https://v.douyin.com/short/"})
    assert response.status_code == 429
    web_app._extraction_slots.release()

    response = client.post("/api/extract", json={"link": "https://v.douyin.com/short/"})
    assert response.status_code == 500
    assert web_app._extraction_slots.acquire(blocking=False)
    web_app._extraction_slots.release()


def test_request_body_limit_uses_json_error_response(client):
    response = client.post(
        "/api/extract",
        data=b"{" + b" " * (64 * 1024),
        content_type="application/json",
    )
    assert response.status_code == 413
    assert response.is_json
