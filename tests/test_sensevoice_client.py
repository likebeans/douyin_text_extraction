"""Offline coverage for model integrity, bounded audio and transcript preservation."""
import hashlib
import io
from pathlib import Path
import sys
import tarfile
from types import SimpleNamespace
import wave

import pytest

import src.sensevoice_client as sensevoice


def model_archive(monkeypatch, *, unsafe=False):
    files = {"model.int8.onnx": b"unit-test-model", "tokens.txt": b"unit-test-tokens"}
    monkeypatch.setattr(sensevoice, "MODEL_FILES", {
        name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in files.items()
    })
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:bz2") as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(f"{sensevoice.MODEL_NAME}/{name}")
            if unsafe and name == "model.int8.onnx":
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside"
                tar.addfile(member)
            else:
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
        unexpected = tarfile.TarInfo("../../unwanted.py")
        unexpected.size = 3
        tar.addfile(unexpected, io.BytesIO(b"bad"))
    data = archive.getvalue()
    monkeypatch.setattr(sensevoice, "MODEL_SHA256", hashlib.sha256(data).hexdigest())

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield data

    monkeypatch.setattr(sensevoice.requests, "get", lambda *a, **kw: Response())
    return files


def test_download_verifies_and_installs_only_named_model_files(tmp_path, monkeypatch):
    files = model_archive(monkeypatch)
    cache = tmp_path / "cache" / "model"
    assert sensevoice._ensure_model(cache) == cache
    assert {p.name for p in cache.iterdir()} == set(files)
    assert all((cache / name).read_bytes() == data for name, data in files.items())
    assert not (tmp_path / "unwanted.py").exists()
    monkeypatch.setattr(sensevoice.requests, "get", lambda *a, **kw: pytest.fail("valid cache downloaded again"))
    assert sensevoice._ensure_model(cache) == cache


def test_bad_download_keeps_existing_files_and_cleans_staging(tmp_path, monkeypatch):
    model_archive(monkeypatch)
    monkeypatch.setattr(sensevoice, "MODEL_SHA256", "0" * 64)
    cache = tmp_path / "cache"
    cache.mkdir()
    old = cache / "model.int8.onnx"
    old.write_bytes(b"existing")
    with pytest.raises(ValueError, match="校验失败"):
        sensevoice._ensure_model(cache)
    assert old.read_bytes() == b"existing"
    assert not list(tmp_path.glob(".sensevoice-*"))


def test_archive_symlink_is_never_installed(tmp_path, monkeypatch):
    model_archive(monkeypatch, unsafe=True)
    with pytest.raises(ValueError, match="格式无效"):
        sensevoice._ensure_model(tmp_path / "cache")
    assert not (tmp_path / "cache").exists()


def test_audio_chunks_bound_duration_without_losing_quiet_samples():
    np = pytest.importorskip("numpy")
    samples = np.linspace(-0.001, 0.001, 69 * sensevoice.SAMPLE_RATE + 13, dtype=np.float32)
    chunks = list(sensevoice._audio_chunks(samples, np))
    assert all(0 < len(chunk) <= 20 * sensevoice.SAMPLE_RATE for chunk in chunks)
    assert np.array_equal(np.concatenate(chunks), samples)
    assert list(sensevoice._audio_chunks(samples[:0], np)) == []


def test_recognition_keeps_repeated_speech_and_uses_one_cached_model(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    calls = []
    texts = iter(["<|zh|><|NEUTRAL|><|Speech|><|withitn|>走吧，走吧。", "走吧，走吧。"])

    class Recognizer:
        def create_stream(self):
            return SimpleNamespace(accept_waveform=lambda *a: None, result=SimpleNamespace(text=""))

        def decode_stream(self, stream):
            stream.result.text = next(texts)

    recognizer = Recognizer()
    module = SimpleNamespace(OfflineRecognizer=SimpleNamespace(
        from_sense_voice=lambda **kwargs: calls.append(kwargs) or recognizer,
    ))
    monkeypatch.setitem(sys.modules, "sherpa_onnx", module)
    monkeypatch.setattr(sensevoice.SenseVoiceClient, "_recognizer", None)
    monkeypatch.setattr(sensevoice, "_ensure_model", lambda path: tmp_path)
    audio = tmp_path / "audio.wav"
    with wave.open(str(audio), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(np.ones(16000, dtype="<i2").tobytes())
    for _ in range(2):
        assert sensevoice.SenseVoiceClient().transcribe(audio) == "走吧，走吧。"
    assert len(calls) == 1
    assert calls[0]["language"] == "zh"


def test_digital_silence_is_empty_and_wrong_audio_format_rejected(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    monkeypatch.setitem(sys.modules, "sherpa_onnx", SimpleNamespace())
    monkeypatch.setattr(sensevoice.SenseVoiceClient, "_recognizer", object())
    audio = tmp_path / "audio.wav"
    with wave.open(str(audio), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(np.zeros(16000, dtype="<i2").tobytes())
    assert sensevoice.SenseVoiceClient().transcribe(audio) == ""
    with wave.open(str(audio), "wb") as output:
        output.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
        output.writeframes(b"\0" * 4)
    with pytest.raises(ValueError, match="16 kHz 单声道"):
        sensevoice.SenseVoiceClient().transcribe(audio)
