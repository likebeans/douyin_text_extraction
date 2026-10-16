"""Fetch video metadata from Douyin's embedded page data."""
from __future__ import annotations

import json
import re
import time
from typing import Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from rich.console import Console
from urllib3.util.retry import Retry

from src.media_url import is_platform_media_url

console = Console()


class VideoMetadata(BaseModel):
    """Metadata needed for transcription and display."""

    video_id: str
    title: str
    author: str
    duration: int
    video_url: str
    cover_url: str = ""


class DouyinFetcher:
    """Retrieve video details by reading the HTML share page."""

    MAX_REDIRECTS = 5
    ALLOWED_HOSTS = {
        "douyin.com",
        "www.douyin.com",
        "m.douyin.com",
        "v.douyin.com",
        "iesdouyin.com",
        "www.iesdouyin.com",
    }
    ROUTER_DATA_PATTERN = re.compile(
        r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.DOTALL | re.IGNORECASE
    )

    def __init__(self, timeout: int = 15, retry_times: int = 3):
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if retry_times < 0:
            raise ValueError("retry_times cannot be negative")
        self.timeout = timeout
        self.retry_times = retry_times
        self.session = requests.Session()
        self._closed = False
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1"
            }
        )
        retry = Retry(
            total=retry_times,
            connect=retry_times,
            read=retry_times,
            status=retry_times,
            backoff_factor=0.2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def close(self) -> None:
        """Close the underlying HTTP session and release adapter pools."""
        if not self._closed:
            self.session.close()
            self.session.adapters.clear()
            self._closed = True

    @classmethod
    def _validated_url(cls, url: str) -> Optional[str]:
        try:
            parts = urlsplit(url)
            port = parts.port
        except (TypeError, ValueError):
            return None
        host = parts.hostname
        if parts.scheme.lower() not in {"http", "https"} or not host:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        if host.lower() not in cls.ALLOWED_HOSTS:
            return None
        if port is not None and port != (443 if parts.scheme.lower() == "https" else 80):
            return None
        netloc = host.lower() + (f":{port}" if port is not None else "")
        return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, parts.fragment))

    @staticmethod
    def _close_response(response) -> None:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    def _get_page(self, url: str):
        """Follow at most five redirects, checking each target before request."""
        current_url = self._validated_url(url)
        if not current_url:
            return None
        for redirect_count in range(self.MAX_REDIRECTS + 1):
            response = None
            try:
                response = self.session.get(
                    current_url,
                    allow_redirects=False,
                    timeout=self.timeout,
                )
                actual_url = self._validated_url(getattr(response, "url", None) or current_url)
                if not actual_url:
                    console.print("[red]❌ 页面返回了非抖音地址[/red]")
                    return None
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        return None
                    next_url = self._validated_url(urljoin(actual_url, location))
                    if not next_url:
                        console.print("[red]❌ 拒绝跟随到非抖音域名的重定向[/red]")
                        return None
                    if redirect_count >= self.MAX_REDIRECTS:
                        console.print("[red]❌ 重定向次数超过限制[/red]")
                        return None
                    current_url = next_url
                    continue
                response.raise_for_status()
                # Parse while the response is open, then close it before returning.
                return actual_url, response.text
            except requests.exceptions.RequestException as exc:
                console.print(f"[red]❌ 网络请求失败: {exc}[/red]")
                return None
            finally:
                if response is not None:
                    self._close_response(response)
        return None

    def _get_video_item(self, video_id: str) -> Optional[dict]:
        share_url = f"https://www.iesdouyin.com/share/video/{video_id}"
        console.print(f"[dim]   访问: {share_url}[/dim]")
        for attempt in range(self.retry_times + 1):
            if attempt:
                time.sleep(min(0.5 * 2 ** (attempt - 1), 2))
            page = self._get_page(share_url)
            if not page:
                # HTTP failures already use the session's bounded retry policy.
                return None
            _, html = page
            match = self.ROUTER_DATA_PATTERN.search(html)
            if not match:
                console.print("[red]❌ 页面未提供视频数据，可能需要在抖音内访问[/red]")
                return None
            try:
                json_data, _ = json.JSONDecoder().raw_decode(match.group(1).strip())
            except json.JSONDecodeError:
                console.print("[red]❌ 页面视频数据格式无效[/red]")
                return None
            loader_data = json_data.get("loaderData") if isinstance(json_data, dict) else None
            if not isinstance(loader_data, dict):
                console.print("[red]❌ 未知的页面数据格式[/red]")
                return None
            page_data = loader_data.get("video_(id)/page") or loader_data.get("note_(id)/page")
            if not isinstance(page_data, dict):
                console.print("[red]❌ 页面未包含视频或笔记详情[/red]")
                return None
            page_id = page_data.get("itemId")
            if page_id is not None and str(page_id) != video_id:
                console.print("[red]❌ 页面视频 ID 与请求不一致[/red]")
                return None
            video_info_res = page_data.get("videoInfoRes")
            if video_info_res is not None:
                if not isinstance(video_info_res, dict):
                    console.print("[red]❌ 视频详情格式无效[/red]")
                    return None
                if video_info_res.get("status_code", 0) != 0:
                    console.print("[red]❌ 平台未允许获取该视频详情[/red]")
                    return None
                item_list = video_info_res.get("item_list")
                if item_list is not None:
                    if not isinstance(item_list, list):
                        console.print("[red]❌ 视频列表格式无效[/red]")
                        return None
                    if item_list:
                        for item in item_list:
                            if isinstance(item, dict) and str(item.get("aweme_id", video_id)) == video_id:
                                return item
                        console.print("[red]❌ 页面未返回匹配的视频详情[/red]")
                        return None
            # Public share pages intermittently omit videoInfoRes even with HTTP 200.
            # Reuse the session, but do not retry explicit denials or invalid responses.
            if attempt < self.retry_times:
                console.print(f"[yellow]⚠ 页面暂未提供视频详情，正在重试（{attempt + 1}/{self.retry_times}）...[/yellow]")
        console.print("[red]❌ 页面多次未提供视频详情，请稍后重试或确认视频可公开访问[/red]")
        return None

    def fetch(self, video_id: str) -> Optional[VideoMetadata]:
        """Fetch metadata for a numeric video or note ID."""
        if not isinstance(video_id, str) or not video_id.isdigit():
            console.print("[red]❌ 视频 ID 必须为数字[/red]")
            return None
        console.print("[cyan]📡 正在获取视频信息...[/cyan]")
        item = self._get_video_item(video_id)
        if item is None:
            return None
        try:
            video_info = item.get("video") or {}
            if not isinstance(video_info, dict):
                video_info = {}
            play_addr = video_info.get("play_addr") or {}
            url_list = play_addr.get("url_list", []) if isinstance(play_addr, dict) else []
            if not url_list or not isinstance(url_list[0], str):
                console.print("[red]❌ 内容不包含可用视频，图文笔记无法转写[/red]")
                return None
            video_url = url_list[0].replace("playwm", "play")
            if not is_platform_media_url(video_url):
                console.print("[red]❌ 页面返回了非平台媒体地址[/red]")
                return None
            title = item.get("desc") or f"douyin_{video_id}"
            author_info = item.get("author") or {}
            author = author_info.get("nickname", "未知作者") if isinstance(author_info, dict) else "未知作者"
            duration = video_info.get("duration", 0)
            if isinstance(duration, (int, float)) and duration >= 1000:
                duration = int(duration // 1000)
            else:
                duration = int(duration or 0)
            cover_info = video_info.get("cover") or {}
            cover_urls = cover_info.get("url_list", []) if isinstance(cover_info, dict) else []
            cover_url = cover_urls[0] if cover_urls else ""
            metadata = VideoMetadata(
                video_id=video_id,
                title=title.strip(),
                author=author,
                duration=duration,
                video_url=video_url,
                cover_url=cover_url,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, IndexError) as exc:
            console.print(f"[red]❌ 数据解析失败: {exc}[/red]")
            return None

        console.print("[green]✅ 视频信息获取成功[/green]")
        console.print(f"   标题: {metadata.title[:50]}{'...' if len(metadata.title) > 50 else ''}")
        console.print(f"   作者: {metadata.author}")
        console.print(f"   时长: {metadata.duration} 秒")
        return metadata
