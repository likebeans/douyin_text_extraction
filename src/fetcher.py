"""抖音视频元数据获取模块 - 基于 HTML 解析"""
import requests
import re
import json
from typing import Optional
from pydantic import BaseModel
from rich.console import Console

console = Console()


class VideoMetadata(BaseModel):
    """视频元数据"""
    video_id: str
    title: str
    author: str
    duration: int  # 秒
    video_url: str  # 无水印视频地址
    cover_url: str = ""
    

class DouyinFetcher:
    """抖音视频元数据获取器 - 基于 HTML 解析
    
    参考 douyin-mcp-server 的实现方式：
    1. 访问分享页面而非 API
    2. 从 HTML 中提取嵌入的 JSON 数据
    3. 解析 window._ROUTER_DATA 对象
    """
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        # 使用移动端 User-Agent（关键！）
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1'
        })
    
    def fetch(self, video_id: str) -> Optional[VideoMetadata]:
        """获取视频元数据
        
        Args:
            video_id: 视频 ID
            
        Returns:
            视频元数据对象，失败返回 None
        """
        console.print("[cyan]📡 正在获取视频信息...[/cyan]")
        
        try:
            # 1. 构建分享 URL
            share_url = f'https://www.iesdouyin.com/share/video/{video_id}'
            console.print(f"[dim]   访问: {share_url}[/dim]")
            
            # 2. 获取 HTML 页面
            response = self.session.get(share_url, timeout=self.timeout)
            response.raise_for_status()
            
            # 3. 从 HTML 中提取 window._ROUTER_DATA JSON
            pattern = re.compile(
                pattern=r"window\._ROUTER_DATA\s*=\s*(.*?)</script>",
                flags=re.DOTALL,
            )
            match = pattern.search(response.text)
            
            if not match or not match.group(1):
                console.print("[red]❌ 无法从 HTML 中提取数据[/red]")
                console.print(f"[dim]   页面内容长度: {len(response.text)}[/dim]")
                return None
            
            # 4. 解析 JSON 数据
            json_str = match.group(1).strip()
            json_data = json.loads(json_str)
            
            # 5. 处理两种内容类型（视频/图文）
            VIDEO_ID_PAGE_KEY = "video_(id)/page"
            NOTE_ID_PAGE_KEY = "note_(id)/page"
            
            loader_data = json_data.get("loaderData", {})
            
            if VIDEO_ID_PAGE_KEY in loader_data:
                console.print("[dim]   检测到视频类型[/dim]")
                original_video_info = loader_data[VIDEO_ID_PAGE_KEY]["videoInfoRes"]
            elif NOTE_ID_PAGE_KEY in loader_data:
                console.print("[dim]   检测到图文/笔记类型[/dim]")
                original_video_info = loader_data[NOTE_ID_PAGE_KEY]["videoInfoRes"]
            else:
                console.print(f"[red]❌ 未知的数据格式[/red]")
                console.print(f"[dim]   loaderData keys: {list(loader_data.keys())}[/dim]")
                return None
            
            # 6. 提取视频详情
            if "item_list" not in original_video_info or not original_video_info["item_list"]:
                console.print("[red]❌ item_list 为空[/red]")
                return None
            
            data = original_video_info["item_list"][0]
            
            # 7. 提取视频播放地址
            video_info = data.get("video", {})
            play_addr = video_info.get("play_addr", {})
            url_list = play_addr.get("url_list", [])
            
            if not url_list:
                console.print("[red]❌ 无法获取视频播放地址[/red]")
                return None
            
            video_url = url_list[0]
            
            # 8. 获取无水印链接（关键步骤！）
            video_url = video_url.replace("playwm", "play")
            
            # 9. 提取其他信息
            title = data.get("desc", "").strip()
            if not title:
                title = f"douyin_{video_id}"
            
            # 替换文件名中的非法字符
            title = re.sub(r'[\\/:*?"<>|]', '_', title)
            
            author_info = data.get("author", {})
            author = author_info.get("nickname", "未知作者")
            
            duration = video_info.get("duration", 0)
            if duration > 1000:  # 如果是毫秒，转换为秒
                duration = duration // 1000
            
            cover_info = video_info.get("cover", {})
            cover_url = ""
            if isinstance(cover_info, dict):
                cover_url_list = cover_info.get("url_list", [])
                if cover_url_list:
                    cover_url = cover_url_list[0]
            
            # 10. 构建元数据对象
            metadata = VideoMetadata(
                video_id=video_id,
                title=title,
                author=author,
                duration=duration,
                video_url=video_url,
                cover_url=cover_url
            )
            
            console.print(f"[green]✅ 视频信息获取成功[/green]")
            console.print(f"   标题: {metadata.title[:50]}{'...' if len(metadata.title) > 50 else ''}")
            console.print(f"   作者: {metadata.author}")
            console.print(f"   时长: {metadata.duration} 秒")
            
            return metadata
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ 网络请求失败: {e}[/red]")
            return None
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ JSON 解析失败: {e}[/red]")
            return None
        except (KeyError, ValueError, IndexError) as e:
            console.print(f"[red]❌ 数据解析失败: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return None
        except Exception as e:
            console.print(f"[red]❌ 未知错误: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return None


if __name__ == "__main__":
    # 测试代码
    fetcher = DouyinFetcher()
    
    # 使用真实的视频 ID 测试
    test_video_id = "7570933456504326888"
    metadata = fetcher.fetch(test_video_id)
    
    if metadata:
        print(f"\n✅ 测试成功！")
        print(f"  视频ID: {metadata.video_id}")
        print(f"  标题: {metadata.title}")
        print(f"  作者: {metadata.author}")
        print(f"  时长: {metadata.duration}秒")
        print(f"  视频URL: {metadata.video_url[:80]}...")
    else:
        print("\n❌ 测试失败")
