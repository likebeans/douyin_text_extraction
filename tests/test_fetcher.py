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


def _page_html(page_data):
    return '<script>window._ROUTER_DATA = ' + json.dumps({
        "loaderData": {"video_(id)/page": page_data},
    }) + ';</script>'


@pytest.mark.parametrize("detail", ["absent", None, {}, {"item_list": []}])
def test_fetch_retries_incomplete_share_data_in_same_session(monkeypatch, detail):
    # Shape observed in live HTTP 200 responses before a complete response.
    page_data = {"itemId": "123", "renderInSSR": 1, "isSpider": False, "commonContext": {}}
    if detail != "absent":
        page_data["videoInfoRes"] = detail
    fetcher = DouyinFetcher(retry_times=2)
    responses = [
        Response(200, "https://www.iesdouyin.com/share/video/123", _page_html(page_data)),
        Response(200, "https://www.iesdouyin.com/share/video/123", _html()),
    ]
    calls = []
    delays = []
    monkeypatch.setattr("src.fetcher.time.sleep", delays.append)

    def get(url, **kwargs):
        calls.append(url)
        return responses[len(calls) - 1]

    fetcher.session.get = get
    try:
        metadata = fetcher.fetch("123")
        assert metadata is not None
        assert metadata.video_url == "https://v3.douyinvod.com/play/video"
        assert len(calls) == 2 and calls[0] == calls[1]
        assert delays == [0.5]
        assert all(response.closed for response in responses)
    finally:
        fetcher.close()


@pytest.mark.parametrize("retries", [0, 2])
def test_incomplete_metadata_retry_budget_is_bounded(monkeypatch, retries):
    fetcher = DouyinFetcher(retry_times=retries)
    calls = []
    monkeypatch.setattr("src.fetcher.time.sleep", lambda _: None)

    def get(url, **kwargs):
        response = Response(200, url, _page_html({"itemId": "123"}))
        calls.append(response)
        return response

    fetcher.session.get = get
    try:
        assert fetcher.fetch("123") is None
        assert len(calls) == retries + 1
        assert all(response.closed for response in calls)
    finally:
        fetcher.close()


@pytest.mark.parametrize("html", [
    "<html>verification required</html>",
    "<script>window._ROUTER_DATA = invalid;</script>",
    "<script>window._ROUTER_DATA = [];</script>",
    _page_html({"itemId": "456"}),
    _page_html({"videoInfoRes": {"status_code": 102, "item_list": []}}),
    _page_html({"videoInfoRes": {"item_list": [{"aweme_id": "456", "video": {}}]}}),
    _page_html({"videoInfoRes": {"item_list": [{"aweme_id": "123", "images": []}]}}),
])
def test_fetch_does_not_retry_denied_invalid_or_nonvideo_pages(monkeypatch, html):
    fetcher = DouyinFetcher(retry_times=2)
    calls = []
    response = Response(200, "https://www.iesdouyin.com/share/video/123", html)
    fetcher.session.get = lambda *args, **kwargs: calls.append(args[0]) or response
    delays = []
    monkeypatch.setattr("src.fetcher.time.sleep", delays.append)
    try:
        assert fetcher.fetch("123") is None
        assert len(calls) == 1
        assert delays == []
        assert response.closed
    finally:
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
