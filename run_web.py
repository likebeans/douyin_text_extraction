#!/usr/bin/env python3
"""运行 Web 应用的便捷脚本"""
import sys
import os
import socket
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from web_app import app, get_local_ip

def main():
    # 从环境变量获取配置，默认值允许外网访问
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # 获取本机 IP
    local_ip = get_local_ip()
    
    print("=" * 70)
    print("🎬 抖音视频文本提取工具 - Web 界面")
    print("=" * 70)
    print(f"📱 本地访问: http://localhost:{port}")
    if host == '0.0.0.0':
        print(f"🌐 局域网访问: http://{local_ip}:{port}")
        print(f"🌍 外网访问配置:")
        print(f"   1. 确保防火墙已开放端口 {port}")
        print(f"   2. 如果使用路由器，需要配置端口转发")
        print(f"   3. 外网访问地址: http://<你的公网IP>:{port}")
    else:
        print(f"⚠️  仅监听 {host}，可能无法外网访问")
    print(f"⚙️  调试模式: {'开启' if debug else '关闭'}")
    print("=" * 70)
    print("💡 提示: 按 Ctrl+C 停止服务")
    print("=" * 70)
    print()
    
    # 确保监听所有接口，并启用多线程
    app.run(debug=debug, host=host, port=port, threaded=True)

if __name__ == '__main__':
    main()
