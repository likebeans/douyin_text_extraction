# 抖音视频文本提取工具启动脚本 (Windows PowerShell)
# 设置 UTF-8 编码以支持 emoji 显示
$env:PYTHONIOENCODING='utf-8'

# 运行主程序，传递所有参数
uv run python main.py $args
