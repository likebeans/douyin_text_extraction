"""抖音链接解析模块"""
import re
import requests
from typing import Optional
from rich.console import Console

console = Console()


class DouyinLinkParser:
    """抖音链接解析器"""
    
    # 正则表达式模式
    SHARE_TEXT_PATTERN = r'(https?://v\.douyin\.com/[A-Za-z0-9]+)'
    VIDEO_ID_PATTERN = r'/video/(\d+)'
    MODAL_ID_PATTERN = r'/modal/detail/(\d+)'
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
        })
    
    def extract_short_url(self, text: str) -> Optional[str]:
        """从分享文本中提取短链接
        
        Args:
            text: 可能包含抖音链接的文本
            
        Returns:
            提取到的短链接，如果没有则返回 None
        """
        match = re.search(self.SHARE_TEXT_PATTERN, text)
        if match:
            return match.group(1)
        
        # 检查是否直接是完整链接
        if 'douyin.com/video/' in text:
            return text
        
        return None
    
    def resolve_redirect(self, short_url: str) -> Optional[str]:
        """解析短链接的重定向
        
        Args:
            short_url: 抖音短链接
            
        Returns:
            重定向后的完整 URL
        """
        try:
            response = self.session.get(
                short_url,
                allow_redirects=True,
                timeout=self.timeout
            )
            return response.url
        except Exception as e:
            console.print(f"[red]❌ 链接重定向失败: {e}[/red]")
            return None
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """从 URL 中提取视频 ID
        
        Args:
            url: 完整的抖音视频 URL
            
        Returns:
            视频 ID (aweme_id)
        """
        # 尝试从 /video/ 路径提取
        match = re.search(self.VIDEO_ID_PATTERN, url)
        if match:
            return match.group(1)
        
        # 尝试从 /modal/detail/ 路径提取
        match = re.search(self.MODAL_ID_PATTERN, url)
        if match:
            return match.group(1)
        
        return None
    
    def parse(self, link_text: str) -> Optional[str]:
        """解析抖音链接，返回视频 ID
        
        Args:
            link_text: 用户输入的链接文本（可能包含分享口令）
            
        Returns:
            视频 ID，解析失败返回 None
        """
        console.print("[cyan]🔍 开始解析链接...[/cyan]")
        
        # 1. 提取短链接
        short_url = self.extract_short_url(link_text)
        if not short_url:
            console.print("[red]❌ 无法从输入中提取有效的抖音链接[/red]")
            return None
        
        console.print(f"[green]✓ 提取到链接: {short_url}[/green]")
        
        # 2. 如果是短链接，需要重定向
        if 'v.douyin.com' in short_url:
            full_url = self.resolve_redirect(short_url)
            if not full_url:
                return None
            console.print(f"[green]✓ 重定向成功[/green]")
        else:
            full_url = short_url
        
        # 3. 提取视频 ID
        video_id = self.extract_video_id(full_url)
        if not video_id:
            console.print("[red]❌ 无法从 URL 中提取视频 ID[/red]")
            return None
        
        console.print(f"[green]✅ 视频 ID: {video_id}[/green]")
        return video_id


if __name__ == "__main__":
    # 测试代码
    parser = DouyinLinkParser()
    
    # 测试用例
    test_links = [
        "https://v.douyin.com/iRNBho6U/",
        "8.32 nkV:/ 复制打开抖音，看看【的作品】# https://v.douyin.com/iRNBho6U/",
        "https://www.douyin.com/video/7445285776618482979"
    ]
    
    for link in test_links:
        print(f"\n测试链接: {link[:50]}...")
        video_id = parser.parse(link)
        print(f"结果: {video_id}\n" + "="*50)
