#!/usr/bin/env python3
"""Start the Flask application with Waitress or explicit local debug mode."""
from __future__ import annotations

import ipaddress
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import Settings
from web_app import app, get_local_ip, load_settings


def _is_loopback_host(host: str) -> bool:
    if host.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> None:
    try:
        settings = load_settings()
    except Exception as error:
        raise SystemExit(f"Web 配置无效: {type(error).__name__}") from None

    host = settings.flask_host
    port = settings.flask_port
    debug = settings.flask_debug
    loopback = _is_loopback_host(host)

    if debug and not loopback:
        raise SystemExit("调试模式只允许绑定本机地址")
    if not loopback and not settings.web_api_token:
        raise SystemExit("绑定非本机地址前必须配置 WEB_API_TOKEN")

    print("=" * 64)
    print("抖音视频文本提取工具 - Web 界面")
    print(f"访问地址: http://{host}:{port}")
    if host in {"0.0.0.0", "::"}:
        print(f"局域网地址: http://{get_local_ip()}:{port}")
    print(f"调试模式: {'开启' if debug else '关闭'}")
    print("=" * 64)

    if debug:
        app.run(debug=True, host=host, port=port, threaded=True)
        return

    try:
        from waitress import serve
    except ImportError:
        raise SystemExit("生产服务器依赖 Waitress 未安装，请运行 uv sync") from None

    logging.basicConfig(level=logging.INFO)
    serve(
        app,
        host=host,
        port=port,
        threads=max(4, settings.web_max_concurrent_extractions + 2),
        connection_limit=100,
        channel_timeout=120,
    )


if __name__ == "__main__":
    main()
