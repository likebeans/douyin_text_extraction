#!/usr/bin/env python3
"""抖音视频文本提取工具 - CLI 主程序"""
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# 导入自定义模块
from src.parser import DouyinLinkParser
from src.fetcher import DouyinFetcher
from src.audio_processor import AudioProcessor
from src.asr_client import ASRClient
from src.local_asr_client import LocalASRClient
from src.formatter import OutputFormatter
from config import settings, ASR_PROVIDER_DASHSCOPE, ASR_PROVIDER_LOCAL

app = typer.Typer(help="抖音视频文本提取工具")
# 在 Windows 上禁用 legacy 模式以支持 Unicode
console = Console(legacy_windows=False)


def show_welcome():
    """显示欢迎信息"""
    welcome = """
    [bold cyan]抖音视频文本提取工具[/bold cyan]
    
    快速将抖音视频转换为可编辑文本
    """
    console.print(Panel(welcome, border_style="cyan"))


@app.command()
def extract(
    link: str = typer.Argument(..., help="抖音视频链接或分享口令"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径（不含扩展名）"),
    format_type: str = typer.Option("md", "--format", "-f", help="输出格式: md/txt/json"),
    no_save: bool = typer.Option(False, "--no-save", help="不保存到文件，仅在终端显示"),
    asr_provider: Optional[str] = typer.Option(None, "--asr-provider", help=f"ASR 提供商: {ASR_PROVIDER_DASHSCOPE}（云端）或 {ASR_PROVIDER_LOCAL}（本地），默认使用配置文件的设置"),
):
    """提取抖音视频的文本内容"""
    
    show_welcome()
    
    # 0. 处理命令行参数覆盖配置
    if asr_provider:
        if asr_provider not in [ASR_PROVIDER_DASHSCOPE, ASR_PROVIDER_LOCAL]:
            console.print(f"[red]❌ 无效的 ASR 提供商: {asr_provider}[/red]")
            console.print(f"[yellow]   支持的值: {ASR_PROVIDER_DASHSCOPE}, {ASR_PROVIDER_LOCAL}[/yellow]")
            raise typer.Exit(code=1)
        settings.asr_provider = asr_provider
        console.print(f"[dim]>> 使用命令行参数覆盖: ASR 提供商 = {asr_provider}[/dim]")
    
    # 1. 检查配置
    if not settings.validate_config():
        if settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
            console.print("[red]❌ 配置错误: 未设置 DASHSCOPE_API_KEY[/red]")
            console.print("[yellow]请设置环境变量或创建 .env 文件，参考 .env.example[/yellow]")
        else:
            console.print("[red]❌ 配置错误: 本地 ASR 需要安装 Whisper[/red]")
            console.print("[yellow]请运行: uv add openai-whisper[/yellow]")
        raise typer.Exit(code=1)
    
    # 2. 解析链接
    parser = DouyinLinkParser()
    video_id = parser.parse(link)
    if not video_id:
        console.print("[red]❌ 链接解析失败[/red]")
        raise typer.Exit(code=1)
    
    # 3. 获取视频元数据
    fetcher = DouyinFetcher()
    metadata = fetcher.fetch(video_id)
    if not metadata:
        console.print("[red]❌ 视频信息获取失败[/red]")
        raise typer.Exit(code=1)
    
    # 检查视频时长限制
    if metadata.duration > settings.max_video_duration:
        console.print(f"[red]❌ 视频时长 ({metadata.duration}s) 超过限制 ({settings.max_video_duration}s)[/red]")
        console.print(f"[yellow]可通过环境变量 MAX_VIDEO_DURATION 调整限制[/yellow]")
        raise typer.Exit(code=1)
    
    # 4. 语音识别（根据配置选择 DashScope 或本地）
    try:
        if settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
            # 使用 DashScope 云端转写（带兜底方案）
            console.print("[cyan]📡 使用 DashScope 云端转写[/cyan]")
            asr_client = ASRClient(settings.dashscope_api_key, settings.asr_model)
            # 使用兜底方案：主方案失败时自动切换到 OSS + FFmpeg
            text = asr_client.transcribe_with_fallback(
                video_url=metadata.video_url,
                video_id=video_id,
                settings=settings
            )
        elif settings.asr_provider == ASR_PROVIDER_LOCAL:
            # 使用本地 Whisper 转写
            console.print("[cyan]💻 使用本地 Whisper 转写[/cyan]")
            # 本地 ASR 需要音频文件，先提取音频
            processor = AudioProcessor()
            audio_path = processor.extract_audio(metadata.video_url)
            if not audio_path:
                console.print("[red]❌ 音频提取失败[/red]")
                raise typer.Exit(code=1)
            
            try:
                local_asr_client = LocalASRClient(model="base")
                text = local_asr_client.transcribe(audio_path=audio_path)
            finally:
                # 清理临时音频文件
                if audio_path.exists():
                    audio_path.unlink()
                    console.print("[dim]>> 已清理临时音频文件[/dim]")
        else:
            console.print(f"[red]❌ 不支持的 ASR 提供商: {settings.asr_provider}[/red]")
            console.print(f"[yellow]   支持的值: {ASR_PROVIDER_DASHSCOPE}, {ASR_PROVIDER_LOCAL}[/yellow]")
            raise typer.Exit(code=1)
        
        if not text:
            console.print("[red]❌ 语音识别失败[/red]")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]❌ 语音识别过程出错: {e}[/red]")
        raise typer.Exit(code=1)
    
    # 5. 格式化输出
    formatter = OutputFormatter()
    
    if format_type == "md":
        content = formatter.format_markdown(
            video_id=metadata.video_id,
            title=metadata.title,
            author=metadata.author,
            duration=metadata.duration,
            text=text,
            video_url=f"https://www.douyin.com/video/{video_id}"
        )
    elif format_type == "txt":
        content = formatter.format_plain_text(
            title=metadata.title,
            author=metadata.author,
            duration=metadata.duration,
            text=text
        )
    else:
        console.print(f"[red]❌ 不支持的格式: {format_type}[/red]")
        raise typer.Exit(code=1)
    
    # 6. 保存或显示结果
    console.print("\n" + "="*60 + "\n")
    
    if not no_save:
        # 保存到文件
        output_filename = output.stem if output else f"douyin_{video_id}"
        saved_path = formatter.save_to_file(
            content,
            settings.output_dir,
            output_filename,
            format_type
        )
        
        if not saved_path:
            raise typer.Exit(code=1)
        
        console.print("\n")
    
    # 在终端显示（Markdown 格式带样式）
    if format_type == "md":
        formatter.print_markdown(content)
    else:
        console.print(content)
    
    console.print("\n[bold green]>> 提取完成！[/bold green]")


@app.command()
def config_check():
    """检查配置是否正确"""
    console.print("[cyan]>> 检查配置...[/cyan]\n")
    
    # 检查必需配置
    console.print("[bold]必需配置:[/bold]")
    if settings.validate_config():
        console.print("[green]✅ DASHSCOPE_API_KEY: 已配置[/green]")
    else:
        console.print("[red]❌ DASHSCOPE_API_KEY: 未配置或为空[/red]")
        console.print("[yellow]   请在 .env 文件中设置 DASHSCOPE_API_KEY[/yellow]")
    
    # 检查 FFmpeg
    console.print("\n[bold]依赖检查:[/bold]")
    processor = AudioProcessor()
    if processor.check_ffmpeg():
        console.print("[green]✅ FFmpeg: 已安装[/green]")
    else:
        console.print("[yellow]⚠️ FFmpeg: 未安装（不影响主功能，但兜底方案需要）[/yellow]")
    
    # 显示 ASR 配置
    console.print(f"\n[bold]ASR 配置:[/bold]")
    provider_name = "DashScope（云端）" if settings.asr_provider == ASR_PROVIDER_DASHSCOPE else "Whisper（本地）"
    console.print(f"  提供商: {provider_name} ({settings.asr_provider})")
    if settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
        console.print(f"  模型: {settings.asr_model}")
    else:
        console.print(f"  模型: Whisper base（本地）")
    console.print(f"  最大视频时长: {settings.max_video_duration}秒")
    
    # 显示输出配置
    console.print(f"\n[bold]输出配置:[/bold]")
    console.print(f"  输出目录: {settings.output_dir}")
    console.print(f"  请求超时: {settings.request_timeout}秒")
    console.print(f"  重试次数: {settings.retry_times}")
    
    # 检查 OSS 配置（如果启用）
    console.print(f"\n[bold]OSS 兜底方案:[/bold]")
    if settings.oss_enable_fallback:
        if settings.validate_oss_config():
            console.print("[green]  ✅ 已启用且配置完整[/green]")
            console.print(f"  Bucket: {settings.oss_bucket_name}")
            console.print(f"  Endpoint: {settings.oss_endpoint}")
            # 测试 OSS 连接
            try:
                from src.oss_client import OSSClient
                oss_client = OSSClient(
                    access_key_id=settings.oss_access_key_id,
                    access_key_secret=settings.oss_access_key_secret,
                    bucket_name=settings.oss_bucket_name,
                    endpoint=settings.oss_endpoint,
                    endpoint_internal=settings.oss_endpoint_internal if settings.oss_endpoint_internal else None,
                    cdn_domain=settings.oss_cdn_domain if settings.oss_cdn_domain else None
                )
                if oss_client.test_connection():
                    console.print(f"[green]  ✅ OSS 连接正常[/green]")
                else:
                    console.print(f"[yellow]  ⚠ OSS 连接失败[/yellow]")
            except Exception as e:
                console.print(f"[yellow]  ⚠ OSS 连接测试异常: {str(e)[:50]}[/yellow]")
        else:
            console.print("[yellow]  ⚠ 已启用但配置不完整[/yellow]")
            console.print("[yellow]  请检查 OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME, OSS_ENDPOINT[/yellow]")
    else:
        console.print("[dim]  未启用（OSS_ENABLE_FALLBACK=false）[/dim]")
        console.print("[dim]  启用后可在主方案失败时自动切换到 OSS + FFmpeg 兜底[/dim]")
    
    console.print()  # 空行


@app.command()
def version():
    """显示版本信息"""
    from src import __version__
    console.print(f"[cyan]douyin-text-extractor[/cyan] v{__version__}")


def main():
    """主入口"""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]>> 用户中断操作[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]❌ 发生错误: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
