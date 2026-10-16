"""Local speech recognition client backed by an optional Whisper install."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


class LocalASRClient:
    """Whisper client sharing loaded models and serializing model inference."""

    _lock = threading.RLock()
    _models = {}
    _whisper_module = None

    def __init__(self, model: str = "base"):
        self.model = model
        self._load_whisper()

    def _load_whisper(self) -> None:
        """Import Whisper lazily, with actionable optional-dependency guidance."""
        cls = type(self)
        with cls._lock:
            if cls._whisper_module is not None:
                return
            try:
                import whisper
            except ImportError as exc:
                console.print("[red]❌ 本地 ASR 需要可选依赖 openai-whisper[/red]")
                console.print("[yellow]   请运行: uv sync --extra local[/yellow]")
                raise ImportError("Install local ASR support with `uv sync --extra local`.") from exc
            cls._whisper_module = whisper

    def transcribe(
        self,
        audio_path: Optional[Path] = None,
        video_url: Optional[str] = None,
    ) -> Optional[str]:
        """Transcribe a local audio file."""
        console.print(f"[cyan]🎤 开始本地语音识别（Whisper {self.model}）...[/cyan]")
        if not audio_path and not video_url:
            console.print("[red]❌ 必须提供 audio_path 或 video_url[/red]")
            return None
        if video_url and not audio_path:
            console.print("[yellow]⚠ 本地 ASR 需要本地音频文件，请先下载并提取音频[/yellow]")
            return None
        audio_path = Path(audio_path)
        if not audio_path.exists():
            console.print(f"[red]❌ 音频文件不存在: {audio_path}[/red]")
            return None

        cls = type(self)
        try:
            console.print(f"[dim]   文件大小: {audio_path.stat().st_size / (1024 * 1024):.2f} MB[/dim]")
            with cls._lock:
                model = cls._models.get(self.model)
                if model is None:
                    # Switching models must not retain several large models in memory.
                    cls._models.clear()
                    model = cls._whisper_module.load_model(self.model)
                    cls._models[self.model] = model
                # Reset each window's text context to avoid propagating repetition loops.
                result = model.transcribe(
                    str(audio_path),
                    language="zh",
                    task="transcribe",
                    condition_on_previous_text=False,
                    beam_size=5,
                    fp16=model.device.type == "cuda",
                    verbose=None,
                )
            text = result.get("text", "").strip()
            console.print(f"[green]✅ 语音识别完成（{len(text)} 字）[/green]")
            if text:
                console.print(f"[dim]   预览: {text[:100]}{'...' if len(text) > 100 else ''}[/dim]")
            return text
        except Exception as exc:
            console.print(f"[red]❌ 本地 ASR 调用异常: {exc}[/red]")
            return None
