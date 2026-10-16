"""CLI 参数、输出和诊断信息的离线测试。"""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

import main
from config import Settings
from src.fetcher import VideoMetadata
from src.service import ExtractionResult

runner = CliRunner()


@pytest.fixture
def cli(monkeypatch, tmp_path):
    settings = Settings(_env_file=None, dashscope_api_key="test-key", output_dir=tmp_path / "output")
    monkeypatch.setattr(main, "load_settings", Mock(return_value=settings))
    result = ExtractionResult(
        VideoMetadata(video_id="123456789", title="标题", author="作者", duration=12, video_url="https://media.example/video.mp4"),
        "第一行\n第二行",
    )
    extractor = Mock()
    extractor.extract.return_value = result
    service_class = Mock(return_value=extractor)
    monkeypatch.setattr(main, "ExtractionService", service_class)
    return settings, extractor, service_class, result


def test_invalid_format_rejected_before_extraction(cli):
    response = runner.invoke(main.app, ["extract", "a link", "--format", "xml"])
    assert response.exit_code == 2
    cli[2].assert_not_called()


def test_json_stdout_remains_parseable_when_service_logs(cli):
    def extract(link):
        print("诊断信息")
        return cli[3]

    cli[1].extract.side_effect = extract
    response = runner.invoke(main.app, ["extract", "a link", "--format", "json", "--no-save"])
    assert response.exit_code == 0, response.output
    data = json.loads(response.stdout)
    assert data["text"] == "第一行\n第二行"
    assert "诊断信息" in response.stderr
    assert not cli[0].output_dir.exists()


@pytest.mark.parametrize("format_type", ["md", "txt", "json"])
def test_absolute_output_path_honored(cli, tmp_path, format_type):
    output = tmp_path / "nested" / f"my.result.{format_type}"
    response = runner.invoke(main.app, ["extract", "a link", "--format", format_type, "--output", str(output)])
    assert response.exit_code == 0, response.output
    assert output.exists()
    assert "第一行" in output.read_text(encoding="utf-8")
    assert not cli[0].output_dir.exists()
    if format_type == "json":
        assert json.loads(response.stdout)["success"] is True


def test_relative_output_directory_honored(cli, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    response = runner.invoke(main.app, ["extract", "a link", "--output", "reports/example", "--format", "txt"])
    assert response.exit_code == 0, response.output
    assert (tmp_path / "reports/example.txt").exists()


def test_bare_filename_uses_output_dir(cli):
    response = runner.invoke(main.app, ["extract", "a link", "--output", "my.report", "--format", "json"])
    assert response.exit_code == 0, response.output
    assert (cli[0].output_dir / "my.report.json").exists()


def test_provider_override_does_not_mutate_next_invocation(monkeypatch):
    monkeypatch.setenv("ASR_PROVIDER", "dashscope")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    assert main.load_settings(main.ASRProvider.local).asr_provider == "local"
    assert main.load_settings().asr_provider == "dashscope"


def test_config_check_failure_has_nonzero_exit(cli, monkeypatch):
    cli[0].dashscope_api_key = ""
    monkeypatch.setattr(main.AudioProcessor, "check_ffmpeg", lambda self: True)
    response = runner.invoke(main.app, ["config-check"])
    assert response.exit_code == 1
    assert "未配置" in response.output
    cli[2].assert_not_called()


def test_config_check_reports_selected_chinese_engine(cli, monkeypatch):
    cli[0].asr_provider = "local"
    cli[0].local_asr_engine = "sensevoice"
    checked = []
    monkeypatch.setattr(main.importlib.util, "find_spec", lambda name: checked.append(name) or object())
    monkeypatch.setattr(main.AudioProcessor, "check_ffmpeg", lambda self: True)
    result = runner.invoke(main.app, ["config-check"])
    assert result.exit_code == 0
    assert "SenseVoiceSmall" in result.output
    assert checked == ["sherpa_onnx", "numpy"]


def test_unexpected_error_does_not_print_secret(cli):
    cli[1].extract.side_effect = RuntimeError("secret-test-key")
    response = runner.invoke(main.app, ["extract", "a link"])
    assert response.exit_code == 1
    assert "secret-test-key" not in response.output
    assert "提取失败" in response.output


def test_version():
    response = runner.invoke(main.app, ["version"])
    assert response.exit_code == 0
    assert "0.3.0" in response.stdout
