"""输出格式化模块"""
from datetime import datetime
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown

console = Console()


class OutputFormatter:
    """输出格式化器"""
    
    @staticmethod
    def format_markdown(
        video_id: str,
        title: str,
        author: str,
        duration: int,
        text: str,
        video_url: str = ""
    ) -> str:
        """格式化为 Markdown
        
        Args:
            video_id: 视频 ID
            title: 视频标题
            author: 作者
            duration: 时长（秒）
            text: 提取的文本
            video_url: 视频链接（可选）
            
        Returns:
            Markdown 格式的文本
        """
        minutes = duration // 60
        seconds = duration % 60
        
        markdown = f"""# 抖音视频文本提取结果

## 📹 视频信息

- **标题**: {title}
- **作者**: {author}
- **时长**: {minutes}:{seconds:02d}
- **视频ID**: {video_id}
"""
        
        if video_url:
            markdown += f"- **链接**: {video_url}\n"
        
        markdown += f"""
---

## 📝 提取文本

{text}

---

*提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        return markdown
    
    @staticmethod
    def format_plain_text(
        title: str,
        author: str,
        duration: int,
        text: str
    ) -> str:
        """格式化为纯文本
        
        Args:
            title: 视频标题
            author: 作者
            duration: 时长（秒）
            text: 提取的文本
            
        Returns:
            纯文本格式
        """
        minutes = duration // 60
        seconds = duration % 60
        
        return f"""抖音视频文本提取结果
{'='*50}

视频信息:
  标题: {title}
  作者: {author}
  时长: {minutes}:{seconds:02d}

{'-'*50}

提取文本:

{text}

{'-'*50}
提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    @staticmethod
    def save_to_file(
        content: str,
        output_dir: Path,
        filename: Optional[str] = None,
        format_type: str = "md"
    ) -> Optional[Path]:
        """保存到文件
        
        Args:
            content: 要保存的内容
            output_dir: 输出目录
            filename: 文件名（不含扩展名），如果为 None 则使用时间戳
            format_type: 文件格式（md/txt）
            
        Returns:
            保存的文件路径，失败返回 None
        """
        try:
            # 确保输出目录存在
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            if filename is None:
                filename = f"douyin_extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 添加扩展名
            file_path = output_dir / f"{filename}.{format_type}"
            
            # 写入文件
            file_path.write_text(content, encoding='utf-8')
            
            console.print(f"[green]✅ 结果已保存到: {file_path}[/green]")
            return file_path
            
        except Exception as e:
            console.print(f"[red]❌ 保存文件失败: {e}[/red]")
            return None
    
    @staticmethod
    def print_markdown(content: str):
        """在终端打印 Markdown（带样式）
        
        Args:
            content: Markdown 内容
        """
        md = Markdown(content)
        console.print(md)


if __name__ == "__main__":
    # 测试代码
    formatter = OutputFormatter()
    
    # 测试 Markdown 格式
    markdown_result = formatter.format_markdown(
        video_id="123456",
        title="测试视频标题",
        author="测试作者",
        duration=125,
        text="这是一段测试文本内容。\n包含多行。",
        video_url="https://example.com/video"
    )
    
    print(markdown_result)
    print("\n" + "="*50 + "\n")
    
    # 测试纯文本格式
    plain_result = formatter.format_plain_text(
        title="测试视频标题",
        author="测试作者",
        duration=125,
        text="这是一段测试文本内容。\n包含多行。"
    )
    
    print(plain_result)
