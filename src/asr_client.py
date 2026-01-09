"""ASR (语音识别) 客户端模块 - 使用阿里云 DashScope 异步 API"""
from pathlib import Path
from typing import Optional
from rich.console import Console
import json
from urllib import request

console = Console()


class ASRClient:
    """阿里云 DashScope ASR 客户端 - 使用异步转写 API
    
    参考 douyin-mcp-server 的实现：
    1. 使用 Transcription.async_call() 提交任务
    2. 使用 Transcription.wait() 等待完成
    3. 从 transcription_url 下载结果
    4. 支持直接使用视频 URL（无需本地文件）
    """
    
    def __init__(self, api_key: str, model: str = "paraformer-v2"):
        """
        Args:
            api_key: DashScope API Key
            model: ASR 模型名称，默认 paraformer-v2
        """
        self.api_key = api_key
        self.model = model
        
        # 延迟导入，避免在没有配置 API Key 时就报错
        try:
            import dashscope
            from http import HTTPStatus
            self.dashscope = dashscope
            self.HTTPStatus = HTTPStatus
            dashscope.api_key = api_key
        except ImportError:
            console.print("[red]❌ dashscope 库未安装，请运行: uv add dashscope[/red]")
            raise
    
    def transcribe(self, audio_path: Optional[Path] = None, video_url: Optional[str] = None) -> Optional[str]:
        """转写音频/视频为文本
        
        Args:
            audio_path: 本地音频文件路径（可选）
            video_url: 视频 URL（推荐，直接使用视频链接，无需下载）
            
        Returns:
            转写文本，失败返回 None
        """
        console.print("[cyan]🎤 开始语音识别...[/cyan]")
        
        # 优先使用视频 URL
        if not video_url and not audio_path:
            console.print("[red]❌ 必须提供 video_url 或 audio_path[/red]")
            return None
        
        if video_url:
            file_url = video_url
            console.print(f"[dim]   使用视频 URL 进行转写[/dim]")
        else:
            if not audio_path.exists():
                console.print(f"[red]❌ 音频文件不存在: {audio_path}[/red]")
                return None
            file_url = f"file://{audio_path.absolute()}"
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            console.print(f"[dim]   文件大小: {file_size_mb:.2f} MB[/dim]")
        
        try:
            # 1. 提交异步转写任务
            console.print(f"[dim]   提交转写任务到 DashScope...[/dim]")
            
            task_response = self.dashscope.audio.asr.Transcription.async_call(
                model=self.model,
                file_urls=[file_url],
                language_hints=['zh', 'en']  # 支持中英文
            )
            
            # 检查任务提交状态
            if task_response.status_code != self.HTTPStatus.OK:
                console.print(f"[red]❌ 提交任务失败[/red]")
                console.print(f"[dim]   状态码: {task_response.status_code}[/dim]")
                console.print(f"[dim]   错误信息: {task_response.message}[/dim]")
                return None
            
            task_id = task_response.output.task_id
            console.print(f"[dim]   任务 ID: {task_id}[/dim]")
            
            # 2. 等待任务完成
            console.print(f"[dim]   等待转写完成（这可能需要一些时间）...[/dim]")
            
            transcription_response = self.dashscope.audio.asr.Transcription.wait(
                task=task_id
            )
            
            # 检查转写状态
            if transcription_response.status_code != self.HTTPStatus.OK:
                console.print(f"[red]❌ 转写失败[/red]")
                console.print(f"[dim]   状态码: {transcription_response.status_code}[/dim]")
                if hasattr(transcription_response, 'message'):
                    console.print(f"[dim]   错误信息: {transcription_response.message}[/dim]")
                if hasattr(transcription_response, 'output'):
                    console.print(f"[dim]   输出: {transcription_response.output}[/dim]")
                return None
            
            # 3. 获取转写结果
            console.print(f"[dim]   任务完成，下载转写结果...[/dim]")
            
            results = transcription_response.output.get('results', [])
            if not results:
                console.print("[red]❌ 没有转写结果[/red]")
                console.print(f"[dim]   响应输出: {transcription_response.output}[/dim]")
                return None
            
            # 检查任务状态
            task_status = results[0].get('subtask_status', 'UNKNOWN')
            if task_status == 'FAILED':
                error_code = results[0].get('code', 'UNKNOWN')
                error_message = results[0].get('message', '未知错误')
                console.print(f"[red]❌ 转写任务失败[/red]")
                console.print(f"[dim]   错误码: {error_code}[/dim]")
                console.print(f"[dim]   错误信息: {error_message}[/dim]")
                return None
            
            # 4. 下载转写结果 JSON
            transcription_url = results[0].get('transcription_url')
            if not transcription_url:
                console.print("[red]❌ 未找到 transcription_url[/red]")
                console.print(f"[dim]   结果内容: {results[0]}[/dim]")
                return None
            
            console.print(f"[dim]   下载地址: {transcription_url[:80]}...[/dim]")
            
            # 下载并解析 JSON
            response_data = request.urlopen(transcription_url).read().decode('utf8')
            result_json = json.loads(response_data)
            
            # 5. 提取文本内容
            if 'transcripts' not in result_json or not result_json['transcripts']:
                console.print("[yellow]⚠ 未检测到语音内容[/yellow]")
                console.print(f"[dim]   结果结构: {list(result_json.keys())}[/dim]")
                return "（音频中未检测到语音内容）"
            
            # 获取转写文本
            text = result_json['transcripts'][0]['text']
            word_count = len(text)
            
            console.print(f"[green]✅ 语音识别完成（{word_count} 字）[/green]")
            console.print(f"[dim]   预览: {text[:100]}{'...' if len(text) > 100 else ''}[/dim]")
            
            return text
            
        except Exception as e:
            console.print(f"[red]❌ ASR 调用异常: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return None
    
    def transcribe_with_timestamp(self, audio_path: Path) -> Optional[list]:
        """带时间戳的转写（进阶功能）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            包含时间戳的转写结果列表
        """
        # TODO: 实现带时间戳的转写
        console.print("[yellow]⚠ 带时间戳的转写功能尚未实现[/yellow]")
        return None


if __name__ == "__main__":
    # 测试代码（需要配置 API Key）
    import os
    
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("❌ 请设置环境变量 DASHSCOPE_API_KEY")
        exit(1)
    
    # 测试视频 URL 转写
    print("\n测试视频 URL 转写...")
    client = ASRClient(api_key)
    
    # 使用一个公开的测试视频 URL
    test_video_url = "https://www.w3schools.com/html/mov_bbb.mp4"
    text = client.transcribe(video_url=test_video_url)
    
    if text:
        print(f"\n✅ 转写成功！")
        print(f"文本: {text[:200]}...")
    else:
        print("\n❌ 转写失败")
