import json
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from src.parser import DouyinLinkParser


@pytest.fixture
def parser():
    instance = DouyinLinkParser(timeout=2, retry_times=0)
    yield instance
    instance.close()


def test_extract_short_link_trims_chinese_punctuation_and_adds_slash(parser):
    assert parser.extract_short_url("复制打开 https://v.douyin.com/abc?x=1，看看") == (
        "https://v.douyin.com/abc/?x=1"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://douyin.com/video/123456",
        "https://www.douyin.com/video/123456",
        "https://m.douyin.com/video/123456",
        "https://v.douyin.com/video/123456",
        "https://iesdouyin.com/share/video/123456",
        "https://www.iesdouyin.com/share/video/123456",
    ],
)
def test_accepts_only_supported_platform_hosts(parser, url):
    expected_url = url
    if urlsplit(url).hostname == "v.douyin.com" and not urlsplit(url).path.endswith(("/123456", "/video/123456")):
        expected_url += "/"
    assert parser.extract_short_url(url) == expected_url
    assert parser.extract_video_id_from_url(url) == "123456"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/video/123456",
        "https://douyin.com.evil.example/video/123456",
        "https://www.douyin.com@evil.example/video/123456",
        "https://user:pass@www.douyin.com/video/123456",
        "https://www.douyin.com:8443/video/123456",
        "ftp://www.douyin.com/video/123456",
    ],
)
def test_rejects_untrusted_hosts_userinfo_ports_and_schemes(parser, url):
    assert parser.extract_short_url(url) is None


@pytest.mark.parametrize("key", ["modal_id", "aweme_id", "item_id", "vid"])
def test_extracts_id_from_query(parser, key):
    assert parser.extract_video_id_from_url(f"https://www.douyin.com/?{key}=123456") == "123456"


def test_extracts_note_path(parser):
    assert parser.extract_video_id_from_url("https://www.douyin.com/note/123456") == "123456"


def test_short_link_redirects_are_checked_one_hop_at_a_time(parser, monkeypatch):
    responses = [
        SimpleNamespace(status_code=302, headers={"Location": "/video/123456"}, url="https://v.douyin.com/abc/", text="", close=lambda: None),
        SimpleNamespace(status_code=200, headers={}, url="https://www.douyin.com/video/123456", text="video page", close=lambda: None),
    ]
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(parser.session, "get", fake_get)
    final_url, html = parser.resolve_redirect("https://v.douyin.com/abc/")

    assert final_url == "https://www.douyin.com/video/123456"
    assert html == "video page"
    assert len(calls) == 2
    assert all(call[1]["allow_redirects"] is False for call in calls)


def test_rejects_redirect_outside_platform_before_request(parser, monkeypatch):
    response = SimpleNamespace(
        status_code=302,
        headers={"Location": "https://attacker.example/video/123456"},
        url="https://v.douyin.com/abc/",
        text="",
        close=lambda: None,
    )
    calls = []
    monkeypatch.setattr(parser.session, "get", lambda *args, **kwargs: calls.append(args) or response)

    assert parser.resolve_redirect("https://v.douyin.com/abc/") == (None, None)
    assert len(calls) == 1


def test_html_json_parser_accepts_trailing_semicolon(parser):
    document = {"loaderData": {"video_(id)/page": {"videoInfoRes": {"item_list": [{"aweme_id": "123456"}]}}}}
    html = f"<script>window._ROUTER_DATA = {json.dumps(document)};</script>"

    assert parser.extract_video_id_from_html(html) == "123456"


def test_short_url_slash_only_changes_path(parser):
    result = parser.extract_short_url("https://v.douyin.com/abc?modal_id=123")
    parts = urlsplit(result)
    assert parts.path == "/abc/"
    assert parts.query == "modal_id=123"
