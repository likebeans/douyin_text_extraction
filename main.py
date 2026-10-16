#!/usr/bin/env python3
"""抖音视频文本提取工具 - CLI。"""
import importlib.util
import json
import sys
from contextlib import redirect_stdout
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError
from rich.console import Console

from config import ASR_PROVIDER_DASHSCOPE, Settings
from src.audio_processor import AudioProcessor
from src.formatter import OutputFormatter
from src.service import ExtractionError, ExtractionService

app = typer.Typer(help="抖音视频文本提取工具")
console = Console(legacy_windows=False, stderr=True)


class OutputFormat(str, Enum):
    md = "md"
    txt = "txt"
    json = "json"


class ASRProvider(str, Enum):
    dashscope = "dashscope"
    local = "local"


def load_settings(provider: Optional[ASRProvider] = None) -> Settings:
    try:
        return Settings(**({"asr_provider": provider.value} if provider else {}))
    except ValidationError as exc:
        fields = ", ".join(str(error["loc"][0]) for error in exc.errors())
        console.print(f"[red]配置无效，请检查：{fields}[/red]")
        raise typer.Exit(code=1) from exc


def output_location(output: Optional[Path], output_dir: Path, video_id: str, format_type: str):
    if output is None:
        return output_dir, f"douyin_{video_id}"
    directory = output.parent if output.is_absolute() or output.parent != Path(".") else output_dir
    suffix = f".{format_type}"
    filename = output.name[:-len(suffix)] if output.name.lower().endswith(suffix) else output.name
    return directory, filename


@app.command()
def extract(
    link: str = typer.Argument(..., help="抖音视频链接或分享口令"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件名或路径，可带对应格式扩展名"),
    format_type: OutputFormat = typer.Option(OutputFormat.md, "--format", "-f", help="输出格式"),
    no_save: bool = typer.Option(False, "--no-save", help="不保存文件，仅输出结果"),
    asr_provider: Optional[ASRProvider] = typer.Option(None, "--asr-provider", help="覆盖本次转写提供商"),
):
    """提取视频文本。JSON 模式将诊断信息写入 stderr，stdout 可直接解析。"""
    current_settings = load_settings(asr_provider)
    try:
        with redirect_stdout(sys.stderr):
            result = ExtractionService(current_settings).extract(link)
    except ExtractionError as exc:
        console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print("提取失败，请检查配置、网络和本地依赖。", style="red")
        raise typer.Exit(code=1) from exc

    formatter = OutputFormatter()
    metadata = result.metadata
    if format_type == OutputFormat.json:
        content = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    elif format_type == OutputFormat.md:
        content = formatter.format_markdown(
            video_id=metadata.video_id,
            title=metadata.title,
            author=metadata.author,
            duration=metadata.duration,
            text=result.text,
            video_url=f"https://www.douyin.com/video/{metadata.video_id}",
        )
    else:
        content = formatter.format_plain_text(
            title=metadata.title,
            author=metadata.author,
            duration=metadata.duration,
            text=result.text,
        )

    if not no_save:
        directory, filename = output_location(output, current_settings.output_dir, metadata.video_id, format_type.value)
        with redirect_stdout(sys.stderr):
            saved_path = formatter.save_to_file(content, directory, filename, format_type.value)
        if saved_path is None:
            raise typer.Exit(code=1)

    if format_type == OutputFormat.md:
        formatter.print_markdown(content)
    else:
        typer.echo(content)


@app.command()
def config_check():
    """离线检查配置及本地依赖，不提交转写任务或访问 OSS。"""
    current_settings = load_settings()
    valid = current_settings.validate_config() and current_settings.validate_oss_config()
    console.print(f"ASR 提供商：{current_settings.asr_provider}")
    if current_settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
        console.print(f"DashScope API Key：{'已配置' if current_settings.dashscope_api_key.strip() else '未配置'}")
        console.print(f"模型：{current_settings.asr_model}")
    else:
        available = importlib.util.find_spec("whisper") is not None
        valid = valid and available
        console.print(f"Whisper：{'已安装' if available else '未安装，请运行 uv sync --extra local'}")
        console.print(f"模型：{current_settings.whisper_model}")

    ffmpeg_available = AudioProcessor().check_ffmpeg()
    console.print(f"FFmpeg：{'已安装' if ffmpeg_available else '未安装'}")
    if current_settings.asr_provider == "local" or current_settings.oss_enable_fallback:
        valid = valid and ffmpeg_available
    console.print(f"OSS 兜底：{'已启用' if current_settings.oss_enable_fallback else '未启用'}")
    if not current_settings.validate_oss_config():
        console.print("OSS 配置不完整，请检查 OSS_ACCESS_KEY_ID / SECRET / BUCKET_NAME / ENDPOINT", style="red")
    console.print(f"最长视频：{current_settings.max_video_duration}秒")
    console.print(f"输出目录：{current_settings.output_dir}", markup=False)
    console.print(f"请求超时：{current_settings.request_timeout}秒；下载时限：{current_settings.download_timeout}秒；ASR 等待：{current_settings.asr_timeout}秒")
    console.print(f"Web 访问令牌：{'已配置' if current_settings.web_api_token else '未配置，仅限本机访问'}")
    if not valid:
        raise typer.Exit(code=1)


@app.command()
def version():
    """显示版本信息。"""
    from src import __version__
    typer.echo(f"douyin-text-extractor v{__version__}")


def main():
    try:
        app()
    except KeyboardInterrupt:
        console.print("已取消操作。", style="yellow")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
