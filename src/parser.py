"""Strict parsing and resolution of Douyin share links."""
from __future__ import annotations

import json
import re
from typing import Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rich.console import Console

console = Console()


class DouyinLinkParser:
    """Extract a video ID from a supported Douyin URL or share message."""

    MAX_REDIRECTS = 5
    ALLOWED_HOSTS = {
        "douyin.com",
        "www.douyin.com",
        "m.douyin.com",
        "v.douyin.com",
        "iesdouyin.com",
        "www.iesdouyin.com",
    }
    VIDEO_ID_PATTERN = re.compile(r"/(?:video|note|modal/detail|share/video)/(\d+)(?:/|$)")
    SHARE_URL_PATTERN = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
    TRAILING_PUNCTUATION = ").,]}>'\"，。！？；：）》】」』”’"

    def __init__(self, timeout: int = 10, retry_times: int = 3):
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
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Referer": "https://www.douyin.com/",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
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

    @classmethod
    def _validated_url(cls, raw_url: str) -> Optional[str]:
        try:
            parts = urlsplit(raw_url.strip())
            host = parts.hostname
            port = parts.port
        except (TypeError, ValueError):
            return None
        if parts.scheme.lower() not in {"http", "https"} or not host:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        if host.lower() not in cls.ALLOWED_HOSTS:
            return None
        if port is not None and port != (443 if parts.scheme.lower() == "https" else 80):
            return None
        # Normalize host spelling and preserve the rest of the URL as supplied.
        netloc = host.lower()
        if port is not None:
            netloc = f"{netloc}:{port}"
        return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, parts.fragment))

    @classmethod
    def _with_short_link_slash(cls, url: str) -> str:
        parts = urlsplit(url)
        canonical_route = re.search(r"/(?:video|note|modal/detail|share/video)/\d+/?$", parts.path)
        if (
            parts.hostname
            and parts.hostname.lower() == "v.douyin.com"
            and parts.path
            and not parts.path.endswith("/")
            and not canonical_route
        ):
            return urlunsplit((parts.scheme, parts.netloc, parts.path + "/", parts.query, parts.fragment))
        return url

    def extract_short_url(self, text: str) -> Optional[str]:
        """Return the first well-formed URL on one of the supported hosts."""
        if not isinstance(text, str):
            return None
        for match in self.SHARE_URL_PATTERN.finditer(text):
            candidate = match.group(0)
            for separator in "，。；：！？、》】）」』":
                candidate = candidate.split(separator, 1)[0]
            candidate = candidate.rstrip(self.TRAILING_PUNCTUATION)
            url = self._validated_url(candidate)
            if url:
                return self._with_short_link_slash(url)
        return None

    def close(self) -> None:
        """Close the underlying HTTP session and release adapter pools."""
        if not self._closed:
            self.session.close()
            self.session.adapters.clear()
            self._closed = True

    @staticmethod
    def _close_response(response) -> None:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    def resolve_redirect(self, short_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Follow redirects manually, validating every destination before use."""
        current_url = self._validated_url(short_url)
        if not current_url:
            console.print("[red]❌ 拒绝访问非抖音链接[/red]")
            return None, None
        current_url = self._with_short_link_slash(current_url)

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
                    console.print("[red]❌ 抖音页面返回了非平台地址[/red]")
                    return None, None
                status = response.status_code
                if status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        return None, None
                    destination = self._validated_url(urljoin(actual_url, location))
                    if not destination:
                        console.print("[red]❌ 拒绝跟随到非抖音域名的重定向[/red]")
                        return None, None
                    if redirect_count >= self.MAX_REDIRECTS:
                        console.print("[red]❌ 重定向次数超过限制[/red]")
                        return None, None
                    console.print(f"[dim]   重定向到: {destination[:100]}[/dim]")
                    current_url = destination
                    continue
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
                elif status >= 400:
                    return None, None
                return actual_url, response.text
            except requests.exceptions.RequestException as exc:
                console.print(f"[red]❌ 链接重定向失败: {exc}[/red]")
                return None, None
            finally:
                if response is not None:
                    self._close_response(response)
        return None, None

    def extract_video_id_from_url(self, url: str) -> Optional[str]:
        """Extract an ID from a supported Douyin URL path or query."""
        validated = self._validated_url(url)
        if not validated:
            return None
        parts = urlsplit(validated)
        match = self.VIDEO_ID_PATTERN.search(parts.path)
        if match:
            return match.group(1)
        for key in ("modal_id", "aweme_id", "item_id", "vid", "video_id", "id"):
            for value in parse_qs(parts.query).get(key, []):
                if value.isdigit():
                    return value
        return None

    def extract_video_id_from_html(self, html: str) -> Optional[str]:
        """Find an ID in router JSON, Open Graph metadata, or page markup."""
        router_match = re.search(
            r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", html, re.DOTALL | re.IGNORECASE
        )
        if router_match:
            raw_json = router_match.group(1).strip()
            try:
                parsed, _ = json.JSONDecoder().raw_decode(raw_json)
                loader_data = parsed.get("loaderData", {})
                for value in loader_data.values():
                    if not isinstance(value, dict):
                        continue
                    video_info = value.get("videoInfoRes", {})
                    items = video_info.get("item_list", []) if isinstance(video_info, dict) else []
                    if items and isinstance(items[0], dict):
                        item = items[0]
                        item_id = item.get("aweme_id") or item.get("item_id") or item.get("video_id")
                        if item_id is not None and str(item_id).isdigit():
                            return str(item_id)
                params = parsed.get("params", {})
                if isinstance(params, dict):
                    for key in ("id", "video_id", "aweme_id", "item_id", "vid", "modal_id"):
                        value = params.get(key)
                        if value is not None and str(value).isdigit():
                            return str(value)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

        meta_matches = re.finditer(
            r"<meta\b[^>]*(?:property|name)=[\"']og:url[\"'][^>]*content=[\"']([^\"']+)",
            html,
            re.IGNORECASE,
        )
        for match in meta_matches:
            video_id = self.extract_video_id_from_url(match.group(1))
            if video_id:
                return video_id

        for match in self.SHARE_URL_PATTERN.finditer(html):
            url = match.group(0).rstrip(self.TRAILING_PUNCTUATION)
            video_id = self.extract_video_id_from_url(url)
            if video_id:
                return video_id

        for match in re.finditer(
            r"(?:video|aweme|item|modal)[_-]?id[\"']?\s*[:=]\s*[\"']?(\d{6,20})",
            html,
            re.IGNORECASE,
        ):
            return match.group(1)
        return None

    def parse(self, link_text: str) -> Optional[str]:
        """Resolve a share message and return its video/note ID."""
        console.print("[cyan]🔍 开始解析链接...[/cyan]")
        share_url = self.extract_short_url(link_text)
        if not share_url:
            console.print("[red]❌ 无法从输入中提取有效的抖音链接[/red]")
            return None
        console.print(f"[green]✓ 提取到链接: {share_url}[/green]")

        if urlsplit(share_url).hostname == "v.douyin.com":
            full_url, html = self.resolve_redirect(share_url)
            if not full_url:
                return None
        else:
            full_url = share_url
            html = None

        video_id = self.extract_video_id_from_url(full_url)
        if not video_id and html:
            video_id = self.extract_video_id_from_html(html)
        if not video_id:
            full_url, html = self.resolve_redirect(full_url)
            if full_url:
                video_id = self.extract_video_id_from_url(full_url)
                if not video_id and html:
                    video_id = self.extract_video_id_from_html(html)

        if not video_id:
            console.print("[red]❌ 无法从 URL 或页面内容中提取视频 ID[/red]")
            return None
        console.print(f"[green]✅ 视频 ID: {video_id}[/green]")
        return video_id
