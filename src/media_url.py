"""平台媒体地址边界，重定向也只能指向已知平台 CDN。"""
from urllib.parse import urlsplit

# 抖音分享页会返回播放 API 或 CDN 地址；新增域名需经过复核。
MEDIA_DOMAINS = (
    "douyin.com", "iesdouyin.com", "snssdk.com", "douyinvod.com",
    "douyincdn.com", "zjcdn.com", "bytecdn.cn", "bytecdn.com",
    "byteimg.com", "ibytedtos.com", "ibyteimg.com", "pstatp.com",
)


def is_platform_media_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme in {"http", "https"}
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443 if parsed.scheme == "https" else 80)
            and any(host == domain or host.endswith("." + domain) for domain in MEDIA_DOMAINS)
        )
    except (TypeError, ValueError):
        return False
