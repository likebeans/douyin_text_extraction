#!/usr/bin/env python3
"""运行 Web 应用的便捷脚本"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from web_app import app

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 抖音视频文本提取工具 - Web 界面")
    print("=" * 60)
    print(f"访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
