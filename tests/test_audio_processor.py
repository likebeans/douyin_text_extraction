from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.audio_processor import AudioProcessor


class StreamResponse:
    def __init__(self, chunks, content_length=None):
        self._chunks = chunks
        self.headers = {} if content_length is None else {"content-length": str(content_length)}
        self.closed = False
        self.status_code = 200

    @property
    def content(self):
        raise AssertionError("stream downloads must not read response.content")

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        assert chunk_size == 8192
        yield from self._chunks

    def close(self):
        self.closed = True


def test_download_always_streams_and_atomically_writes_file(tmp_path, monkeypatch):
    response = StreamResponse([b"video", b"data"])
    calls = []
    monkeypatch.setattr("src.audio_processor.requests.get", lambda *args, **kwargs: calls.append(kwargs) or response)
    destination = tmp_path / "video.mp4"

    result = AudioProcessor(temp_dir=tmp_path).download_video("https://v3.douyinvod.com/video", destination)

    assert result == destination
    assert destination.read_bytes() == b"videodata"
    assert calls[0]["stream"] is True
    assert 0 < calls[0]["timeout"] <= 30
    assert calls[0]["allow_redirects"] is False
    assert response.closed
    assert not list(tmp_path.glob(".download-*.part"))


def test_download_rejects_content_length_over_limit_and_cleans_partial_file(tmp_path, monkeypatch):
    response = StreamResponse([b"too big"], content_length=8)
    monkeypatch.setattr("src.audio_processor.requests.get", lambda *args, **kwargs: response)
    destination = tmp_path / "video.mp4"

    assert AudioProcessor(temp_dir=tmp_path, max_download_bytes=4).download_video(
        "https://v3.douyinvod.com/video", destination
    ) is None
    assert not destination.exists()
    assert response.closed
    assert not list(tmp_path.glob(".download-*.part"))


def test_download_enforces_streamed_byte_limit(tmp_path, monkeypatch):
    response = StreamResponse([b"123", b"456"])
    monkeypatch.setattr("src.audio_processor.requests.get", lambda *args, **kwargs: response)

    result = AudioProcessor(max_download_bytes=4).download_video(
        "https://v3.douyinvod.com/video", tmp_path / "video.mp4"
    )

    assert result is None
    assert response.closed
    assert not list(tmp_path.glob(".download-*.part"))


def test_download_enforces_total_elapsed_timeout(tmp_path, monkeypatch):
    response = StreamResponse([b"video"])
    monkeypatch.setattr("src.audio_processor.requests.get", lambda *args, **kwargs: response)
    monkeypatch.setattr("src.audio_processor.time.monotonic", lambda: 0)
    monkeypatch.setattr("src.audio_processor.time.time", lambda: 0)

    # The patched clock advances after the first chunk is received.
    values = iter([0, 0, 2])
    monkeypatch.setattr("src.audio_processor.time.monotonic", lambda: next(values))
    destination = tmp_path / "video.mp4"

    assert AudioProcessor(download_timeout=1).download_video("https://v3.douyinvod.com/video", destination) is None
    assert not destination.exists()
    assert response.closed


def test_extract_audio_uses_secure_staging_path_and_removes_failure_output(tmp_path, monkeypatch):
    monkeypatch.setattr(AudioProcessor, "check_ffmpeg", lambda self: True)

    def fail(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial")
        return SimpleNamespace(returncode=1, stderr="decode failed")

    monkeypatch.setattr("src.audio_processor.subprocess.run", fail)
    destination = tmp_path / "result.wav"

    result = AudioProcessor(temp_dir=tmp_path).extract_audio("video.mp4", destination)

    assert result is None
    assert not destination.exists()
    assert not list(tmp_path.glob(".audio-*.wav"))


def test_extract_audio_atomically_moves_successful_result(tmp_path, monkeypatch):
    monkeypatch.setattr(AudioProcessor, "check_ffmpeg", lambda self: True)

    def succeed(command, **kwargs):
        assert kwargs["timeout"] == 120
        Path(command[-1]).write_bytes(b"wav")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("src.audio_processor.subprocess.run", succeed)
    destination = tmp_path / "result.wav"

    result = AudioProcessor(temp_dir=tmp_path).extract_audio("video.mp4", destination)

    assert result == destination
    assert destination.read_bytes() == b"wav"
    assert not list(tmp_path.glob(".audio-*.wav"))


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/private",
    "http://169.254.169.254/latest/meta-data/",
    "https://douyinvod.com.attacker.example/video",
    "https://douyinvod.com@attacker.example/video",
    "https://v3.douyinvod.com:8443/video",
    "file:///etc/passwd",
])
def test_download_rejects_non_platform_targets_before_request(tmp_path, monkeypatch, url):
    get = Mock()
    monkeypatch.setattr("src.audio_processor.requests.get", get)
    destination = tmp_path / "video.mp4"

    assert AudioProcessor().download_video(url, destination) is None
    get.assert_not_called()
    assert not destination.exists()


def test_download_checks_redirect_target_before_following(tmp_path, monkeypatch):
    response = StreamResponse([])
    response.status_code = 302
    response.headers["Location"] = "http://127.0.0.1/private"
    get = Mock(return_value=response)
    monkeypatch.setattr("src.audio_processor.requests.get", get)
    destination = tmp_path / "video.mp4"

    assert AudioProcessor().download_video("https://v3.douyinvod.com/video", destination) is None
    get.assert_called_once()
    assert get.call_args.kwargs["allow_redirects"] is False
    assert response.closed
    assert not destination.exists()


def test_download_follows_valid_relative_redirect_with_remaining_timeout(tmp_path, monkeypatch):
    redirect = StreamResponse([])
    redirect.status_code = 302
    redirect.headers["Location"] = "/actual-video"
    video = StreamResponse([b"video"])
    get = Mock(side_effect=[redirect, video])
    monkeypatch.setattr("src.audio_processor.requests.get", get)
    ticks = iter([0, 1, 4, 5, 6])
    monkeypatch.setattr("src.audio_processor.time.monotonic", lambda: next(ticks))
    destination = tmp_path / "video.mp4"

    assert AudioProcessor(timeout=10, download_timeout=10).download_video("https://v3.douyinvod.com/video", destination) == destination
    assert get.call_args_list[1].args[0] == "https://v3.douyinvod.com/actual-video"
    assert [call.kwargs["timeout"] for call in get.call_args_list] == [9, 6]
    assert all(call.kwargs["allow_redirects"] is False for call in get.call_args_list)
    assert redirect.closed and video.closed
    assert destination.read_bytes() == b"video"


def test_download_can_outlast_request_timeout_while_data_keeps_arriving(tmp_path, monkeypatch):
    response = StreamResponse([b"first", b"second"])
    get = Mock(return_value=response)
    monkeypatch.setattr("src.audio_processor.requests.get", get)
    ticks = iter([0, 0, 20, 20, 40, 40])
    monkeypatch.setattr("src.audio_processor.time.monotonic", lambda: next(ticks))
    destination = tmp_path / "video.mp4"

    result = AudioProcessor(timeout=30, download_timeout=300).download_video(
        "https://v3.douyinvod.com/video", destination,
    )

    assert result == destination
    assert destination.read_bytes() == b"firstsecond"
    assert get.call_args.kwargs["timeout"] == 30
    assert response.closed


def test_download_bounds_redirect_count(tmp_path, monkeypatch):
    responses = [StreamResponse([]) for _ in range(6)]
    for response in responses:
        response.status_code = 302
        response.headers["Location"] = "/loop"
    get = Mock(side_effect=responses)
    monkeypatch.setattr("src.audio_processor.requests.get", get)

    assert AudioProcessor().download_video("https://v3.douyinvod.com/video", tmp_path / "video.mp4") is None
    assert get.call_count == 6
    assert all(response.closed for response in responses)


def test_ffmpeg_timeout_is_independent_and_cleans_partial_output(tmp_path, monkeypatch):
    monkeypatch.setattr(AudioProcessor, "check_ffmpeg", lambda self: True)

    def time_out(command, **kwargs):
        assert kwargs["timeout"] == 90
        Path(command[-1]).write_bytes(b"partial")
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("src.audio_processor.subprocess.run", time_out)
    destination = tmp_path / "result.wav"
    destination.write_bytes(b"previous result")

    result = AudioProcessor(temp_dir=tmp_path, timeout=7, ffmpeg_timeout=90).extract_audio("video.mp4", destination)

    assert result is None
    assert destination.read_bytes() == b"previous result"
    assert not list(tmp_path.glob(".audio-*.wav"))
