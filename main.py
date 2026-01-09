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
from src.formatter import OutputFormatter
from config import settings

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
):
    """提取抖音视频的文本内容"""
    
    show_welcome()
    
    # 1. 检查配置
    if not settings.validate_config():
        console.print("[red]❌ 配置错误: 未设置 DASHSCOPE_API_KEY[/red]")
        console.print("[yellow]请设置环境变量或创建 .env 文件，参考 .env.example[/yellow]")
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
    
    # 4. 语音识别（直接使用视频 URL，无需提取音频）
    try:
        asr_client = ASRClient(settings.dashscope_api_key, settings.asr_model)
        
        # 使用视频 URL 直接进行转写（更快、更省空间）
        text = asr_client.transcribe(video_url=metadata.video_url)
        
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
    
    # 检查 API Key
    if settings.validate_config():
        console.print("[green]✅ DASHSCOPE_API_KEY: 已配置[/green]")
    else:
        console.print("[red]❌ DASHSCOPE_API_KEY: 未配置或无效[/red]")
    
    # 检查 FFmpeg
    processor = AudioProcessor()
    if processor.check_ffmpeg():
        console.print("[green]✅ FFmpeg: 已安装[/green]")
    else:
        console.print("[red]❌ FFmpeg: 未安装[/red]")
    
    # 显示其他配置
    console.print(f"\n[cyan]其他配置:[/cyan]")
    console.print(f"  最大视频时长: {settings.max_video_duration}秒")
    console.print(f"  ASR 模型: {settings.asr_model}")
    console.print(f"  输出目录: {settings.output_dir}")


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
