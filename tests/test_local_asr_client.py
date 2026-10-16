import sys
import threading
import time
from types import ModuleType, SimpleNamespace

import pytest

from src.local_asr_client import LocalASRClient


def _fake_whisper(monkeypatch, model):
    module = ModuleType("whisper")
    calls = []
    module.load_model = lambda name: calls.append(name) or model
    monkeypatch.setitem(sys.modules, "whisper", module)
    return calls


def test_whisper_model_is_cached_across_client_instances(tmp_path, monkeypatch):
    load_calls = []
    transcription_calls = []

    class Model:
        device = SimpleNamespace(type="cpu")

        def transcribe(self, path, **kwargs):
            transcription_calls.append((path, kwargs))
            return {"text": " recognized "}

    _fake_whisper(monkeypatch, Model())
    monkeypatch.setattr(LocalASRClient, "_models", {})
    monkeypatch.setattr(LocalASRClient, "_whisper_module", None)
    module = sys.modules["whisper"]
    module.load_model = lambda name: load_calls.append(name) or Model()
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")

    assert LocalASRClient("base").transcribe(audio_path=audio_path) == "recognized"
    assert LocalASRClient("base").transcribe(audio_path=audio_path) == "recognized"
    assert load_calls == ["base"]
    assert len(transcription_calls) == 2


def test_inference_is_serialized_for_shared_cached_model(tmp_path, monkeypatch):
    active = 0
    maximum_active = 0
    active_lock = threading.Lock()

    class Model:
        device = SimpleNamespace(type="cpu")

        def transcribe(self, path, **kwargs):
            nonlocal active, maximum_active
            with active_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.02)
            with active_lock:
                active -= 1
            return {"text": "ok"}

    _fake_whisper(monkeypatch, Model())
    monkeypatch.setattr(LocalASRClient, "_models", {})
    monkeypatch.setattr(LocalASRClient, "_whisper_module", None)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    clients = [LocalASRClient("base") for _ in range(3)]
    results = []
    threads = [threading.Thread(target=lambda client=client: results.append(client.transcribe(audio_path))) for client in clients]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results == ["ok", "ok", "ok"]
    assert maximum_active == 1


@pytest.mark.parametrize("device", ["cpu", "cuda"])
def test_decoding_resets_context_and_preserves_spoken_repetitions(tmp_path, monkeypatch, device):
    spoken = "走吧，走吧。吃吃吃！过了一会儿又说：走吧。"
    received = {}
    model = SimpleNamespace(device=SimpleNamespace(type=device))

    def transcribe(path, **options):
        received.update(options)
        return {"text": f"  {spoken}  "}

    model.transcribe = transcribe
    _fake_whisper(monkeypatch, model)
    monkeypatch.setattr(LocalASRClient, "_models", {})
    monkeypatch.setattr(LocalASRClient, "_whisper_module", None)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")

    assert LocalASRClient("base").transcribe(audio_path) == spoken
    assert received["condition_on_previous_text"] is False
    assert received["beam_size"] == 5
    assert received["fp16"] is (device == "cuda")
    # Keep Whisper's low-confidence retry and silence defaults; do not inject words.
    assert "temperature" not in received
    assert "initial_prompt" not in received
    assert "no_speech_threshold" not in received


def test_changing_models_releases_previous_cached_model(tmp_path, monkeypatch):
    model = SimpleNamespace(
        device=SimpleNamespace(type="cpu"),
        transcribe=lambda *args, **kwargs: {"text": "文本"},
    )
    load_calls = _fake_whisper(monkeypatch, model)
    monkeypatch.setattr(LocalASRClient, "_models", {})
    monkeypatch.setattr(LocalASRClient, "_whisper_module", None)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    base = LocalASRClient("base")
    turbo = LocalASRClient("turbo")

    for client in (base, turbo, turbo, base):
        assert client.transcribe(audio_path) == "文本"
        assert list(LocalASRClient._models) == [client.model]
    assert load_calls == ["base", "turbo", "base"]
