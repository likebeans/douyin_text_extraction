import json

import pytest

from src.fetcher import DouyinFetcher


class Response:
    def __init__(self, status_code, url, text="", headers=None):
        self.status_code = status_code
        self.url = url
        self.text = text
        self.headers = headers or {}
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad status")

    def close(self):
        self.closed = True


def _html(duration=1000, title="A:/ original title", video_url="https://v3.douyinvod.com/playwm/video"):
    payload = {
        "loaderData": {
            "video_(id)/page": {
                "videoInfoRes": {
                    "item_list": [
                        {
                            "desc": title,
                            "author": {"nickname": "author"},
                            "video": {
                                "duration": duration,
                                "play_addr": {"url_list": [video_url]},
                                "cover": {"url_list": ["https://cdn.example/cover"]},
                            },
                        }
                    ]
                }
            }
        }
    }
    return f"<script>window._ROUTER_DATA = {json.dumps(payload)};</script>;"


def test_fetcher_retries_get_only_and_closes_session():
    fetcher = DouyinFetcher(timeout=4, retry_times=1)
    adapter = fetcher.session.get_adapter("https://")
    assert adapter.max_retries.total == 1
    assert adapter.max_retries.allowed_methods == frozenset({"GET"})
    session = fetcher.session
    fetcher.close()
    assert session is fetcher.session
    assert session.adapters == {}


def test_fetch_parses_semicolon_duration_boundary_and_preserves_title():
    fetcher = DouyinFetcher()
    response = Response(200, "https://www.iesdouyin.com/share/video/123", _html())
    fetcher.session.get = lambda *args, **kwargs: response

    metadata = fetcher.fetch("123")

    assert metadata is not None
    assert metadata.duration == 1
    assert metadata.title == "A:/ original title"
    assert metadata.video_url == "https://v3.douyinvod.com/play/video"
    assert response.closed
    fetcher.close()


def test_fetcher_rejects_non_platform_redirect_without_following():
    fetcher = DouyinFetcher()
    response = Response(
        302,
        "https://www.iesdouyin.com/share/video/123",
        headers={"Location": "https://attacker.example/video"},
    )
    requests_seen = []

    def get(url, **kwargs):
        requests_seen.append((url, kwargs))
        return response

    fetcher.session.get = get

    assert fetcher.fetch("123") is None
    assert len(requests_seen) == 1
    assert requests_seen[0][1]["allow_redirects"] is False
    assert response.closed
    fetcher.close()


def test_fetch_rejects_non_numeric_video_ids():
    fetcher = DouyinFetcher()
    assert fetcher.fetch("123/../../other") is None
    fetcher.close()


@pytest.mark.parametrize("video_url", [
    "http://127.0.0.1/private",
    "https://douyinvod.com.attacker.example/video",
    "https://user:password@v3.douyinvod.com/video",
])
def test_fetch_rejects_non_platform_playback_url(video_url):
    fetcher = DouyinFetcher()
    response = Response(200, "https://www.iesdouyin.com/share/video/123", _html(video_url=video_url))
    fetcher.session.get = lambda *args, **kwargs: response

    assert fetcher.fetch("123") is None
    assert response.closed
    fetcher.close()
