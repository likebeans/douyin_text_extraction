import io
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from src.asr_client import ASRClient


def _install_dashscope(monkeypatch, transcription):
    monkeypatch.setitem(
        sys.modules,
        "dashscope",
        SimpleNamespace(
            audio=SimpleNamespace(asr=SimpleNamespace(Transcription=transcription)),
            base_http_api_url="https://dashscope.test/api/v1",
        ),
    )


def _response(status, output):
    return SimpleNamespace(status_code=status, output=output, message="ok")


def test_transcribe_uses_explicit_key_finite_polling_and_download_timeout(monkeypatch):
    transcription = SimpleNamespace(
        async_call=Mock(return_value=_response(200, SimpleNamespace(task_id="task-1"))),
    )
    _install_dashscope(monkeypatch, transcription)
    payloads = [
        {"output": {"task_status": "RUNNING"}},
        {"output": {"task_status": "SUCCEEDED", "results": [{"transcription_url": "https://result.example/r.json"}]}},
        {"transcripts": [{"text": "recognized"}]},
    ]
    urlopen = Mock(side_effect=[io.BytesIO(json.dumps(payload).encode()) for payload in payloads])
    monkeypatch.setattr("src.asr_client.request.urlopen", urlopen)
    monkeypatch.setattr("src.asr_client.time.sleep", lambda _: None)
    client = ASRClient("private-key", request_timeout=7, asr_timeout=20)

    assert client.transcribe(video_url="https://cdn.example/video") == "recognized"
    assert transcription.async_call.call_args.kwargs["api_key"] == "private-key"
    assert transcription.async_call.call_args.kwargs["request_timeout"] == 7
    assert urlopen.call_count == 3
    for call in urlopen.call_args_list[:2]:
        assert call.args[0].full_url == "https://dashscope.test/api/v1/tasks/task-1"
        assert call.args[0].get_header("Authorization") == "Bearer private-key"
        assert 0 < call.kwargs["timeout"] <= 7
    assert urlopen.call_args.args == ("https://result.example/r.json",)
    assert urlopen.call_args.kwargs["timeout"] == 7
    assert not hasattr(sys.modules["dashscope"], "api_key")


def test_transcribe_returns_none_when_task_deadline_expires(monkeypatch):
    transcription = SimpleNamespace(async_call=Mock(return_value=_response(200, SimpleNamespace(task_id="task-1"))))
    _install_dashscope(monkeypatch, transcription)
    urlopen = Mock(return_value=io.BytesIO(json.dumps({"output": {"task_status": "RUNNING"}}).encode()))
    monkeypatch.setattr("src.asr_client.request.urlopen", urlopen)
    ticks = iter([0, 0, 2])
    monkeypatch.setattr("src.asr_client.time.monotonic", lambda: next(ticks))
    monkeypatch.setattr("src.asr_client.time.sleep", lambda _: None)
    client = ASRClient("key", asr_timeout=1)

    assert client.transcribe(video_url="https://cdn.example/video") is None
    urlopen.assert_called_once()
    assert urlopen.call_args.kwargs["timeout"] == 1


def test_fallback_uses_unique_temp_dirs_preserves_when_configured_and_deletes_oss(
    tmp_path, monkeypatch
):
    created_dirs = []

    class Processor:
        def __init__(self, temp_dir, **kwargs):
            self.temp_dir = temp_dir

        def download_video(self, video_url, save_path):
            save_path.write_bytes(b"video")
            return save_path

        def extract_audio(self, video_source, output_path=None):
            output_path.write_bytes(b"audio")
            return output_path

    class OSS:
        def __init__(self, **kwargs):
            self.deleted = []

        def upload_audio(self, audio_path):
            return "https://oss.example/audio", "remote/audio.wav"

        def delete_file(self, path):
            self.deleted.append(path)

    oss_clients = []
    oss_kwargs = []

    def make_oss(**kwargs):
        oss_kwargs.append(kwargs)
        client = OSS(**kwargs)
        oss_clients.append(client)
        return client

    monkeypatch.setattr("src.audio_processor.AudioProcessor", Processor)
    monkeypatch.setattr("src.oss_client.OSSClient", make_oss)
    config = SimpleNamespace(
        oss_enable_fallback=True,
        validate_oss_config=lambda: True,
        temp_dir=tmp_path,
        cleanup_temp_files=False,
        request_timeout=9,
        download_timeout=300,
        asr_timeout=10,
        ffmpeg_timeout=120,
        max_download_bytes=1000,
        oss_access_key_id="id",
        oss_access_key_secret="secret",
        oss_bucket_name="bucket",
        oss_endpoint="endpoint",
        oss_endpoint_internal="",
        oss_cdn_domain="",
    )
    client = ASRClient.__new__(ASRClient)
    client.transcribe = Mock(side_effect=[None, "fallback text", None, "fallback text"])

    assert client.transcribe_with_fallback("https://video.example/v", "123", config) == "fallback text"
    assert client.transcribe_with_fallback("https://video.example/v", "123", config) == "fallback text"
    for oss in oss_clients:
        assert oss.deleted == ["remote/audio.wav"]
    created_dirs = list(tmp_path.iterdir())
    assert len(created_dirs) == 2
    assert created_dirs[0] != created_dirs[1]
    assert all((path / "video.mp4").exists() and (path / "audio.wav").exists() for path in created_dirs)
    assert all(kwargs["request_timeout"] == 9 for kwargs in oss_kwargs)
    assert all(kwargs["sign_url_expires"] == 3600 for kwargs in oss_kwargs)


def test_fallback_cleans_unique_temp_dir_even_when_oss_is_deleted(tmp_path, monkeypatch):
    class Processor:
        def __init__(self, temp_dir, **kwargs):
            self.temp_dir = temp_dir

        def download_video(self, video_url, save_path):
            save_path.write_bytes(b"video")
            return save_path

        def extract_audio(self, video_source, output_path=None):
            output_path.write_bytes(b"audio")
            return output_path

    class OSS:
        def __init__(self, **kwargs):
            self.deleted = []

        def upload_audio(self, audio_path):
            return "https://oss.example/audio", "remote/audio.wav"

        def delete_file(self, path):
            self.deleted.append(path)

    oss_clients = []
    monkeypatch.setattr("src.audio_processor.AudioProcessor", Processor)
    monkeypatch.setattr("src.oss_client.OSSClient", lambda **kwargs: oss_clients.append(OSS(**kwargs)) or oss_clients[-1])
    config = SimpleNamespace(
        oss_enable_fallback=True,
        validate_oss_config=lambda: True,
        temp_dir=tmp_path,
        cleanup_temp_files=True,
        request_timeout=9,
        download_timeout=300,
        asr_timeout=10,
        ffmpeg_timeout=120,
        max_download_bytes=1000,
        oss_access_key_id="id",
        oss_access_key_secret="secret",
        oss_bucket_name="bucket",
        oss_endpoint="endpoint",
        oss_endpoint_internal="",
        oss_cdn_domain="",
    )
    client = ASRClient.__new__(ASRClient)
    client.transcribe = Mock(side_effect=[None, "fallback text"])

    assert client.transcribe_with_fallback("https://video.example/v", "123", config) == "fallback text"
    assert list(tmp_path.iterdir()) == []
    assert oss_clients[0].deleted == ["remote/audio.wav"]
