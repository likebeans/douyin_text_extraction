"""共享处理流程的离线回归测试。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

import pytest

from config import Settings
from src.fetcher import VideoMetadata
from src.service import ExtractionError, ExtractionService
import src.service as service


@pytest.fixture
def configured(tmp_path):
    return Settings(_env_file=None, dashscope_api_key="unit-test-key", temp_dir=tmp_path / "temp")


@pytest.fixture
def dependencies(monkeypatch):
    parser = Mock()
    parser.parse.return_value = "7445285776618482979"
    fetcher = Mock()
    fetcher.fetch.return_value = VideoMetadata(
        video_id="7445285776618482979",
        title="视频：测试标题",
        author="测试作者",
        duration=42,
        video_url="https://media.example/video.mp4",
    )
    cloud = Mock()
    cloud.transcribe_with_fallback.return_value = " 转写文本 \n"
    parser_class = Mock(return_value=parser)
    fetcher_class = Mock(return_value=fetcher)
    cloud_class = Mock(return_value=cloud)
    monkeypatch.setattr(service, "DouyinLinkParser", parser_class)
    monkeypatch.setattr(service, "DouyinFetcher", fetcher_class)
    monkeypatch.setattr(service, "ASRClient", cloud_class)
    return parser, fetcher, cloud, parser_class, fetcher_class, cloud_class


def test_cloud_uses_fallback_and_configured_timeouts(configured, dependencies):
    parser, fetcher, cloud, parser_class, fetcher_class, cloud_class = dependencies
    configured.request_timeout = 7
    configured.retry_times = 2
    configured.asr_timeout = 90
    result = ExtractionService(configured).extract("https://www.douyin.com/video/7445285776618482979")
    assert result.text == "转写文本"
    assert result.to_dict()["metadata"]["douyin_url"].endswith("7445285776618482979")
    parser_class.assert_called_once_with(timeout=7, retry_times=2)
    fetcher_class.assert_called_once_with(timeout=7, retry_times=2)
    cloud_class.assert_called_once_with("unit-test-key", "paraformer-v2", request_timeout=7, asr_timeout=90)
    cloud.transcribe_with_fallback.assert_called_once_with(
        video_url=fetcher.fetch.return_value.video_url,
        video_id=parser.parse.return_value,
        settings=configured,
    )
    parser.close.assert_called_once()
    fetcher.close.assert_called_once()


@pytest.mark.parametrize("link", [None, 42, "", " \n", "x" * 8193])
def test_invalid_link_rejected_before_clients(configured, dependencies, link):
    with pytest.raises(ExtractionError):
        ExtractionService(configured).extract(link)
    dependencies[3].assert_not_called()


def test_cloud_credentials_checked_before_network(configured, dependencies):
    configured.dashscope_api_key = " "
    with pytest.raises(ExtractionError, match="DASHSCOPE_API_KEY"):
        ExtractionService(configured).extract("https://www.douyin.com/video/1")
    dependencies[3].assert_not_called()


def test_failed_parse_closes_clients(configured, dependencies):
    dependencies[0].parse.return_value = None
    with pytest.raises(ExtractionError, match="链接解析失败"):
        ExtractionService(configured).extract("bad input")
    dependencies[0].close.assert_called_once()
    dependencies[1].close.assert_called_once()
    dependencies[1].fetch.assert_not_called()


def test_duration_rejected_before_asr(configured, dependencies):
    dependencies[1].fetch.return_value.duration = configured.max_video_duration + 1
    with pytest.raises(ExtractionError, match="超过限制"):
        ExtractionService(configured).extract("https://www.douyin.com/video/1")
    dependencies[5].assert_not_called()


def test_local_dependency_preflight(configured, dependencies, monkeypatch):
    configured.asr_provider = "local"
    monkeypatch.setattr(service, "LocalASRClient", Mock(side_effect=ImportError("whisper")))
    with pytest.raises(ExtractionError, match="uv sync --extra local"):
        ExtractionService(configured).extract("https://www.douyin.com/video/1")
    dependencies[3].assert_not_called()


@pytest.mark.parametrize("cleanup", [True, False])
@pytest.mark.parametrize("failure", ["download", "audio", "transcribe", None])
def test_local_workspace_lifecycle(configured, dependencies, monkeypatch, cleanup, failure):
    configured.asr_provider = "local"
    configured.cleanup_temp_files = cleanup
    processor = Mock()
    processor.check_ffmpeg.return_value = True
    paths = []

    def download(url, path):
        paths.append(path)
        path.write_bytes(b"video")
        return None if failure == "download" else path

    def extract_audio(source, output_path):
        output_path.write_bytes(b"audio")
        return None if failure == "audio" else output_path

    processor.download_video.side_effect = download
    processor.extract_audio.side_effect = extract_audio
    local = Mock()
    if failure == "transcribe":
        local.transcribe.side_effect = RuntimeError("local failure")
    else:
        local.transcribe.return_value = "本地文本"
    monkeypatch.setattr(service, "AudioProcessor", Mock(return_value=processor))
    monkeypatch.setattr(service, "LocalASRClient", Mock(return_value=local))
    if failure:
        with pytest.raises((ExtractionError, RuntimeError)):
            ExtractionService(configured).extract("https://www.douyin.com/video/1")
    else:
        assert ExtractionService(configured).extract("https://www.douyin.com/video/1").text == "本地文本"
    assert bool(list(configured.temp_dir.iterdir())) is not cleanup
    assert paths[0].parent.exists() is not cleanup


def test_successful_local_result_survives_cleanup_failure(configured, dependencies, monkeypatch, caplog):
    configured.asr_provider = "local"
    configured.ffmpeg_timeout = 85
    processor = Mock()
    processor.check_ffmpeg.return_value = True
    processor.download_video.side_effect = lambda url, path: path
    processor.extract_audio.side_effect = lambda source, output_path: output_path
    processor_class = Mock(return_value=processor)
    local = Mock()
    local.transcribe.return_value = "已成功转写"
    monkeypatch.setattr(service, "AudioProcessor", processor_class)
    monkeypatch.setattr(service, "LocalASRClient", Mock(return_value=local))
    cleanup = Mock(side_effect=OSError("cleanup failed"))
    monkeypatch.setattr(service.shutil, "rmtree", cleanup)

    result = ExtractionService(configured).extract("https://www.douyin.com/video/1")

    assert result.text == "已成功转写"
    assert processor_class.call_args.kwargs["ffmpeg_timeout"] == 85
    cleanup.assert_called_once()
    assert "临时目录清理失败" in caplog.text


def test_same_video_concurrently_uses_independent_workspaces(configured, dependencies, monkeypatch):
    configured.asr_provider = "local"
    gate = Barrier(2)
    paths = []
    processor = Mock()
    processor.check_ffmpeg.return_value = True

    def download(url, path):
        paths.append(path)
        path.write_bytes(b"video")
        gate.wait(timeout=5)
        return path

    def extract_audio(source, output_path):
        assert source.exists()
        output_path.write_bytes(b"audio")
        return output_path

    processor.download_video.side_effect = download
    processor.extract_audio.side_effect = extract_audio
    local = Mock()
    local.transcribe.return_value = "文本"
    monkeypatch.setattr(service, "AudioProcessor", Mock(return_value=processor))
    monkeypatch.setattr(service, "LocalASRClient", Mock(return_value=local))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: ExtractionService(configured).extract("https://www.douyin.com/video/1"), range(2)))
    assert all(result.text == "文本" for result in results)
    assert paths[0].parent != paths[1].parent
    assert not list(configured.temp_dir.iterdir())
