"""Platform CDN boundaries, including the cold-media redirect host."""
import pytest

from src.media_url import is_platform_media_url


@pytest.mark.parametrize("url", [
    "https://idouyinvod.com/video",
    "https://rw964n-41.free-lbv13.idouyinvod.com/video",
    "https://v13-cold.douyinvod.com/video",
])
def test_platform_media_cdn_is_allowed(url):
    assert is_platform_media_url(url)


@pytest.mark.parametrize("url", [
    "https://idouyinvod.com.attacker.example/video",
    "https://fakeidouyinvod.com/video",
    "https://idouyinvod.com@attacker.example/video",
    "https://user:password@idouyinvod.com/video",
    "https://rw964n-41.free-lbv13.idouyinvod.com:8443/video",
    "http://127.0.0.1/video",
])
def test_cdn_allowlist_still_rejects_unrelated_targets(url):
    assert not is_platform_media_url(url)
