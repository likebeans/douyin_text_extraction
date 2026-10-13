import sys
import threading
import time
from types import ModuleType

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
