#!/usr/bin/env python3
"""抖音视频文本提取工具 - Web 应用"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv, set_key, dotenv_values

from src.parser import DouyinLinkParser
from src.fetcher import DouyinFetcher
from src.asr_client import ASRClient
from config import Settings

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 全局实例
parser = DouyinLinkParser()
fetcher = DouyinFetcher()
# 配置实例会在每次请求时重新加载
settings = Settings()

# 确保输出目录存在
output_dir = Path("./output")
output_dir.mkdir(exist_ok=True)

# .env 文件路径
ENV_FILE = Path(".env")


def get_env_config() -> Dict[str, str]:
    """获取当前 .env 配置"""
    if ENV_FILE.exists():
        return dotenv_values(ENV_FILE)
    return {}


def save_env_config(config: Dict[str, str]) -> bool:
    """保存配置到 .env 文件"""
    try:
        # 读取现有配置
        env_values = get_env_config()
        # 更新配置
        env_values.update(config)
        # 写入文件
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            for key, value in env_values.items():
                if value:
                    f.write(f"{key}={value}\n")
        # 重新加载配置
        load_dotenv(ENV_FILE, override=True)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/config')
def config_page():
    """配置页面"""
    # 重新加载配置以确保显示最新值
    load_dotenv(ENV_FILE, override=True)
    current_settings = Settings()
    
    env_config = get_env_config()
    # 获取当前配置的默认值
    config = {
        'DASHSCOPE_API_KEY': env_config.get('DASHSCOPE_API_KEY', current_settings.dashscope_api_key),
        'MAX_VIDEO_DURATION': env_config.get('MAX_VIDEO_DURATION', str(current_settings.max_video_duration)),
        'ASR_MODEL': env_config.get('ASR_MODEL', current_settings.asr_model),
        'OUTPUT_DIR': env_config.get('OUTPUT_DIR', str(current_settings.output_dir)),
    }
    # 隐藏 API Key 的显示（只显示前几位）
    api_key = config['DASHSCOPE_API_KEY']
    if api_key and len(api_key) > 10:
        masked_key = api_key[:10] + "..."
    else:
        masked_key = api_key if api_key else ""
    
    return render_template('config.html', config=config, masked_key=masked_key)


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置 API"""
    # 重新加载配置
    load_dotenv(ENV_FILE, override=True)
    current_settings = Settings()
    
    env_config = get_env_config()
    config = {
        'DASHSCOPE_API_KEY': env_config.get('DASHSCOPE_API_KEY', ''),
        'MAX_VIDEO_DURATION': env_config.get('MAX_VIDEO_DURATION', str(current_settings.max_video_duration)),
        'ASR_MODEL': env_config.get('ASR_MODEL', current_settings.asr_model),
        'OUTPUT_DIR': env_config.get('OUTPUT_DIR', str(current_settings.output_dir)),
    }
    # 隐藏敏感信息
    api_key = config['DASHSCOPE_API_KEY']
    if api_key and len(api_key) > 10:
        config['DASHSCOPE_API_KEY'] = api_key[:10] + "..."
    else:
        config['DASHSCOPE_API_KEY'] = api_key if api_key else ""
    
    return jsonify({
        'success': True,
        'config': config
    })


@app.route('/api/config', methods=['POST'])
def save_config():
    """保存配置 API"""
    data = request.get_json()
    
    # 验证必填字段
    if 'DASHSCOPE_API_KEY' not in data or not data['DASHSCOPE_API_KEY']:
        return jsonify({
            'success': False,
            'error': 'DASHSCOPE_API_KEY 是必填项'
        }), 400
    
    # 重新加载当前配置以获取默认值
    load_dotenv(ENV_FILE, override=True)
    current_settings = Settings()
    
    # 准备要保存的配置
    config_to_save = {
        'DASHSCOPE_API_KEY': data['DASHSCOPE_API_KEY'].strip(),
        'MAX_VIDEO_DURATION': data.get('MAX_VIDEO_DURATION', str(current_settings.max_video_duration)).strip(),
        'ASR_MODEL': data.get('ASR_MODEL', current_settings.asr_model).strip(),
    }
    
    # 可选配置
    if data.get('OUTPUT_DIR'):
        config_to_save['OUTPUT_DIR'] = data['OUTPUT_DIR'].strip()
    
    # 保存配置
    if save_env_config(config_to_save):
        return jsonify({
            'success': True,
            'message': '配置保存成功'
        })
    else:
        return jsonify({
            'success': False,
            'error': '配置保存失败'
        }), 500


@app.route('/api/extract', methods=['POST'])
def extract_video():
    """提取视频文本 API"""
    data = request.get_json()
    link = data.get('link', '').strip()
    
    if not link:
        return jsonify({
            'success': False,
            'error': '请提供抖音链接'
        }), 400
    
    # 重新加载配置以确保使用最新设置
    load_dotenv(ENV_FILE, override=True)
    current_settings = Settings()
    
    # 检查配置
    if not current_settings.validate_config():
        return jsonify({
            'success': False,
            'error': '配置错误: 未设置 DASHSCOPE_API_KEY，请先到配置页面设置'
        }), 400
    
    try:
        # 1. 解析链接
        video_id = parser.parse(link)
        if not video_id:
            return jsonify({
                'success': False,
                'error': '链接解析失败，请检查链接是否正确'
            }), 400
        
        # 2. 获取视频元数据
        metadata = fetcher.fetch(video_id)
        if not metadata:
            return jsonify({
                'success': False,
                'error': '视频信息获取失败，请检查链接是否有效'
            }), 400
        
        # 检查视频时长限制
        if metadata.duration > current_settings.max_video_duration:
            return jsonify({
                'success': False,
                'error': f'视频时长 ({metadata.duration}秒) 超过限制 ({current_settings.max_video_duration}秒)'
            }), 400
        
        # 3. 语音识别
        asr_client = ASRClient(current_settings.dashscope_api_key, current_settings.asr_model)
        text = asr_client.transcribe(video_url=metadata.video_url)
        
        if not text:
            return jsonify({
                'success': False,
                'error': '语音识别失败，请检查 API Key 是否有效'
            }), 500
        
        # 4. 返回结果
        result = {
            'success': True,
            'metadata': {
                'video_id': metadata.video_id,
                'title': metadata.title,
                'author': metadata.author,
                'duration': metadata.duration,
                'video_url': metadata.video_url,
                'cover_url': metadata.cover_url,
                'douyin_url': f"https://www.douyin.com/video/{metadata.video_id}"
            },
            'text': text
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'处理失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
