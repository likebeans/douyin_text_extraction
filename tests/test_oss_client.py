"""OSS client unit tests; live integration is explicitly opt-in."""
from pathlib import Path

import pytest

from src.oss_client import OSSClient


def make_client(config=None):
    config = config or {}
    return OSSClient(
        access_key_id=config.get("OSS_ACCESS_KEY_ID", "test-key-id"),
        access_key_secret=config.get("OSS_ACCESS_KEY_SECRET", "test-key-secret"),
        bucket_name=config.get("OSS_BUCKET_NAME", "test-bucket"),
        endpoint=config.get("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com"),
        endpoint_internal=config.get("OSS_ENDPOINT_INTERNAL") or None,
        cdn_domain=config.get("OSS_CDN_DOMAIN") or None,
    )


def test_oss_client_initialization_without_network():
    client = make_client()
    assert client.bucket_name == "test-bucket"
    assert client.endpoint == "oss-cn-hangzhou.aliyuncs.com"
    assert client.bucket is not None


def test_upload_nonexistent_file_returns_none(tmp_path):
    client = make_client()
    assert client.upload_audio(tmp_path / "missing.wav") is None


@pytest.mark.integration
def test_real_oss_upload_and_delete(tmp_path, integration_oss_env):
    """This writes and deletes one object in the explicitly configured bucket."""
    audio_file = tmp_path / "integration-test.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 100)
    client = make_client(integration_oss_env)
    uploaded = client.upload_audio(audio_file)
    assert uploaded is not None
    url, object_path = uploaded
    assert url.startswith("https://")
    assert object_path.startswith("douyin_audio/")
    try:
        assert client.bucket.object_exists(object_path)
    finally:
        client.delete_file(object_path)
