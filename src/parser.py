"""抖音链接解析模块"""
import re
import requests
import json
from typing import Optional, Tuple
from rich.console import Console

console = Console()


class DouyinLinkParser:
    """抖音链接解析器"""
    
    # 正则表达式模式
    SHARE_TEXT_PATTERN = r'(https?://v\.douyin\.com/[A-Za-z0-9_]+)'
    VIDEO_ID_PATTERN = r'/video/(\d+)'
    MODAL_ID_PATTERN = r'/modal/detail/(\d+)'
    # 支持更多 URL 格式
    VIDEO_ID_IN_URL_PATTERN = r'(?:/video/|video/|/share/video/)(\d+)'
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1'
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
    
    def resolve_redirect(self, short_url: str) -> Tuple[Optional[str], Optional[str]]:
        """解析短链接的重定向，返回重定向后的 URL 和 HTML 内容
        
        Args:
            short_url: 抖音短链接
            
        Returns:
            (重定向后的完整 URL, HTML 内容) 的元组
        """
        try:
            response = self.session.get(
                short_url,
                allow_redirects=True,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.url, response.text
        except Exception as e:
            console.print(f"[red]❌ 链接重定向失败: {e}[/red]")
            return None, None
    
    def extract_video_id_from_url(self, url: str) -> Optional[str]:
        """从 URL 中提取视频 ID
        
        Args:
            url: 完整的抖音视频 URL
            
        Returns:
            视频 ID (aweme_id) 或 None
        """
        # 尝试多种 URL 格式
        patterns = [
            self.VIDEO_ID_PATTERN,  # /video/123456789
            self.MODAL_ID_PATTERN,  # /modal/detail/123456789
            self.VIDEO_ID_IN_URL_PATTERN,  # 通用匹配
            r'video_id["\']?\s*[:=]\s*["\']?(\d+)',  # JSON 中的 video_id
            r'aweme_id["\']?\s*[:=]\s*["\']?(\d+)',  # JSON 中的 aweme_id
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def extract_video_id_from_html(self, html: str) -> Optional[str]:
        """从 HTML 页面中提取视频 ID
        
        Args:
            html: HTML 页面内容
            
        Returns:
            视频 ID (aweme_id) 或 None
        """
        try:
            # 方法1: 从 window._ROUTER_DATA 提取
            pattern = re.compile(
                r"window\._ROUTER_DATA\s*=\s*(.*?)</script>",
                re.DOTALL
            )
            match = pattern.search(html)
            if match:
                json_str = match.group(1).strip()
                json_data = json.loads(json_str)
                
                # 查找视频 ID 在 loaderData 中（参考 fetcher.py 的实现）
                loader_data = json_data.get("loaderData", {})
                
                # 处理两种内容类型（视频/图文）
                VIDEO_ID_PAGE_KEY = "video_(id)/page"
                NOTE_ID_PAGE_KEY = "note_(id)/page"
                
                # 首先尝试标准格式
                if VIDEO_ID_PAGE_KEY in loader_data:
                    try:
                        video_info_res = loader_data[VIDEO_ID_PAGE_KEY].get("videoInfoRes", {})
                        item_list = video_info_res.get("item_list", [])
                        if item_list and len(item_list) > 0:
                            aweme_id = item_list[0].get("aweme_id") or item_list[0].get("item_id")
                            if aweme_id:
                                return str(aweme_id)
                    except (KeyError, IndexError, TypeError):
                        pass
                
                if NOTE_ID_PAGE_KEY in loader_data:
                    try:
                        video_info_res = loader_data[NOTE_ID_PAGE_KEY].get("videoInfoRes", {})
                        item_list = video_info_res.get("item_list", [])
                        if item_list and len(item_list) > 0:
                            aweme_id = item_list[0].get("aweme_id") or item_list[0].get("item_id")
                            if aweme_id:
                                return str(aweme_id)
                    except (KeyError, IndexError, TypeError):
                        pass
                
                # 尝试从其他键中查找
                for key, value in loader_data.items():
                    if isinstance(value, dict):
                        try:
                            # 检查是否有 videoInfoRes
                            if "videoInfoRes" in value:
                                video_info_res = value["videoInfoRes"]
                                item_list = video_info_res.get("item_list", [])
                                if item_list and len(item_list) > 0:
                                    aweme_id = item_list[0].get("aweme_id") or item_list[0].get("item_id")
                                    if aweme_id:
                                        return str(aweme_id)
                        except (KeyError, IndexError, TypeError):
                            continue
                
                # 尝试从 URL 路径参数中提取
                if "params" in json_data:
                    params = json_data["params"]
                    video_id = params.get("id") or params.get("video_id") or params.get("aweme_id")
                    if video_id:
                        return str(video_id)
            
            # 方法2: 从页面 meta 标签提取
            meta_pattern = re.compile(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)
            match = meta_pattern.search(html)
            if match:
                og_url = match.group(1)
                video_id = self.extract_video_id_from_url(og_url)
                if video_id:
                    return video_id
            
            # 方法3: 从页面中直接搜索数字 ID（备用方法）
            # 搜索常见的视频 ID 格式（19位数字）
            id_pattern = re.compile(r'(?:video|aweme)[_-]?id["\']?\s*[:=]\s*["\']?(\d{15,20})')
            match = id_pattern.search(html)
            if match:
                return match.group(1)
                
        except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
            console.print(f"[dim]   从 HTML 提取视频 ID 失败: {e}[/dim]")
        
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
        
        # 2. 如果是短链接，需要重定向并获取 HTML
        html_content = None
        if 'v.douyin.com' in short_url:
            full_url, html_content = self.resolve_redirect(short_url)
            if not full_url:
                return None
            console.print(f"[green]✓ 重定向成功: {full_url[:80]}...[/green]")
        else:
            full_url = short_url
        
        # 3. 首先尝试从 URL 中提取视频 ID
        video_id = self.extract_video_id_from_url(full_url)
        
        # 4. 如果无法从 URL 提取，尝试从 HTML 中提取
        if not video_id and html_content:
            console.print("[cyan]   尝试从页面内容中提取视频 ID...[/cyan]")
            video_id = self.extract_video_id_from_html(html_content)
        
        # 5. 如果还是没有，尝试直接请求页面
        if not video_id:
            console.print("[cyan]   尝试直接请求页面...[/cyan]")
            try:
                response = self.session.get(full_url, timeout=self.timeout)
                response.raise_for_status()
                video_id = self.extract_video_id_from_html(response.text)
            except Exception as e:
                console.print(f"[dim]   直接请求失败: {e}[/dim]")
        
        if not video_id:
            console.print("[red]❌ 无法从 URL 或页面内容中提取视频 ID[/red]")
            console.print(f"[dim]   请检查链接是否有效: {full_url}[/dim]")
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
