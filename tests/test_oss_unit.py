"""OSS 传输与签名行为，只使用模拟 Bucket。"""
from unittest.mock import Mock

import pytest

import src.oss_client as module
from src.oss_client import OSSClient


@pytest.fixture
def buckets(monkeypatch):
    created = []

    def create(auth, endpoint, bucket_name, **kwargs):
        bucket = Mock()
        bucket.put_object.return_value.status = 200
        bucket.sign_url.return_value = "https://bucket.oss.example/audio?signature=unit-test"
        created.append((endpoint, bucket))
        return bucket

    monkeypatch.setattr(module.oss2, "Bucket", create)
    return created


def test_private_bucket_uses_temporary_signed_url(tmp_path, buckets):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"audio")
    client = OSSClient("test-id", "test-secret", "bucket", "oss.example")
    url, key = client.upload_audio(path)
    assert buckets[0][0] == "https://oss.example"
    assert "signature=" in url
    buckets[0][1].sign_url.assert_called_once_with("GET", key, 3600)


def test_consecutive_uploads_get_different_object_names(tmp_path, buckets):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"audio")
    client = OSSClient("test-id", "test-secret", "bucket", "oss.example")
    _, first_key = client.upload_audio(path)
    _, second_key = client.upload_audio(path)
    assert first_key != second_key


def test_internal_endpoint_does_not_escape_into_signed_url(tmp_path, buckets):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"audio")
    client = OSSClient("test-id", "test-secret", "bucket", "oss.example", endpoint_internal="oss-internal.example")
    _, key = client.upload_audio(path)
    assert [endpoint for endpoint, _ in buckets] == ["https://oss-internal.example", "https://oss.example"]
    buckets[0][1].put_object.assert_called_once()
    buckets[1][1].sign_url.assert_called_once_with("GET", key, 3600)
    client.delete_file(key)
    buckets[0][1].delete_object.assert_called_once_with(key)


def test_cdn_url_is_https_and_encodes_object_name(tmp_path, buckets):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"audio")
    client = OSSClient("test-id", "test-secret", "bucket", "oss.example", cdn_domain="https://cdn.example/")
    url, _ = client.upload_audio(path, remote_path="folder/a b.wav")
    assert url == "https://cdn.example/folder/a%20b.wav"


@pytest.mark.parametrize("endpoint", ["", "https://user:secret@oss.example", "ftp://oss.example", "https://oss.example/path", "https://oss.example?x=1"])
def test_invalid_endpoint_rejected(endpoint, buckets):
    with pytest.raises(ValueError):
        OSSClient("test-id", "test-secret", "bucket", endpoint)
