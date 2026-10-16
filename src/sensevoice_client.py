"""Optional Chinese ASR using SenseVoiceSmall through sherpa-onnx."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import threading
import time
import wave

import requests
from rich.console import Console

console = Console()
MODEL_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
MODEL_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{MODEL_NAME}.tar.bz2"
MODEL_SHA256 = "7d1efa2138a65b0b488df37f8b89e3d91a60676e416f515b952358d83dfd347e"
MODEL_FILES = {
    "model.int8.onnx": (239233841, "c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51"),
    "tokens.txt": (315894, "f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc"),
}
SAMPLE_RATE = 16000
CONTROL_TAGS = re.compile(
    r"<\|(?:zh|en|ja|ko|yue|nospeech|NEUTRAL|HAPPY|SAD|ANGRY|FEARFUL|DISGUSTED|"
    r"SURPRISED|Speech|BGM|Applause|Laughter|Cry|Sneeze|Breath|Cough|Sing|"
    r"Speech_Noise|Event_UNK|EMO_UNKNOWN|withitn|woitn)\|>"
)


def _file_matches(path: Path, size: int, digest: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest() == digest


def _ensure_model(cache: Path) -> Path:
    """Install only verified, named files; never extract archive scripts or paths."""
    if all(_file_matches(cache / name, *expected) for name, expected in MODEL_FILES.items()):
        return cache
    console.print("[cyan]首次使用 SenseVoiceSmall，下载模型约 163 MB...[/cyan]")
    console.print("[dim]模型：FunASR / FunAudioLLM；权重许可见 docs/ASR_PROVIDER_GUIDE.md[/dim]")
    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sensevoice-", dir=cache.parent) as directory:
        staging = Path(directory)
        archive = staging / "model.tar.bz2"
        started = time.monotonic()
        checksum = hashlib.sha256()
        downloaded = 0
        with requests.get(MODEL_URL, stream=True, timeout=(15, 30)) as response:
            response.raise_for_status()
            with archive.open("wb") as target:
                for chunk in response.iter_content(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > 200 * 1024 * 1024 or time.monotonic() - started > 600:
                        raise ValueError("SenseVoice 模型下载超过大小或时间限制")
                    checksum.update(chunk)
                    target.write(chunk)
        if checksum.hexdigest() != MODEL_SHA256:
            raise ValueError("SenseVoice 模型校验失败，请重试下载")
        extracted = set()
        # Streaming avoids decompressing this archive repeatedly for each member.
        with tarfile.open(archive, "r|bz2") as source:
            for member in source:
                name = member.name.removeprefix(f"{MODEL_NAME}/")
                if name not in MODEL_FILES or member.name != f"{MODEL_NAME}/{name}":
                    continue
                if name in extracted or not member.isfile() or member.size != MODEL_FILES[name][0]:
                    raise ValueError("SenseVoice 模型包格式无效")
                with source.extractfile(member) as item, (staging / name).open("xb") as target:
                    shutil.copyfileobj(item, target)
                extracted.add(name)
        if extracted != set(MODEL_FILES) or not all(
            _file_matches(staging / name, *expected) for name, expected in MODEL_FILES.items()
        ):
            raise ValueError("SenseVoice 模型文件校验失败")
        cache.mkdir(parents=True, exist_ok=True)
        for name in MODEL_FILES:
            os.replace(staging / name, cache / name)
    return cache


def _audio_chunks(samples, np):
    """Bound each chunk to 20 seconds and cut near quiet audio without dropping samples."""
    start = 0
    maximum = 20 * SAMPLE_RATE
    frame = SAMPLE_RATE // 10
    while start < len(samples):
        end = min(start + maximum, len(samples))
        if end < len(samples):
            search_start = start + 12 * SAMPLE_RATE
            frames = samples[search_start:end].reshape(-1, frame)
            energy = np.mean(frames * frames, axis=1)
            end = search_start + int(np.argmin(energy)) * frame + frame // 2
        yield samples[start:end]
        start = end


class SenseVoiceClient:
    """Serialize CPU inference and share a single verified model across requests."""

    _lock = threading.RLock()
    _recognizer = None

    def __init__(self):
        try:
            import numpy
            import sherpa_onnx
        except ImportError as exc:
            raise ImportError("Install Chinese ASR with `uv sync --extra local-chinese`.") from exc
        self._np = numpy
        self._sherpa = sherpa_onnx

    def transcribe(self, audio_path: Path) -> str:
        console.print("[cyan]🎤 开始本地语音识别（SenseVoiceSmall）...[/cyan]")
        with wave.open(str(audio_path), "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, SAMPLE_RATE):
                raise ValueError("SenseVoice 需要 16 kHz 单声道 PCM WAV")
            samples = self._np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(self._np.float32) / 32768
        if not len(samples) or not self._np.any(samples):
            return ""
        cls = type(self)
        with cls._lock:
            if cls._recognizer is None:
                cache_root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
                model_dir = _ensure_model(cache_root / "douyin-text-extractor" / MODEL_NAME)
                cls._recognizer = self._sherpa.OfflineRecognizer.from_sense_voice(
                    model=str(model_dir / "model.int8.onnx"),
                    tokens=str(model_dir / "tokens.txt"),
                    language="zh",
                    use_itn=True,
                    num_threads=4,
                    provider="cpu",
                )
            texts = []
            for chunk in _audio_chunks(samples, self._np):
                # Exact digital silence needs no inference. Keep even very quiet speech.
                if not self._np.any(chunk):
                    continue
                stream = cls._recognizer.create_stream()
                stream.accept_waveform(SAMPLE_RATE, chunk)
                cls._recognizer.decode_stream(stream)
                text = CONTROL_TAGS.sub("", stream.result.text).strip()
                if text:
                    texts.append(text)
        text = "\n".join(texts)
        console.print(f"[green]✅ 语音识别完成（{len(text)} 字）[/green]")
        return text
