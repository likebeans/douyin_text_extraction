#!/usr/bin/env python3
"""抖音视频文本提取工具 - Web 应用"""
import os
import json
import socket
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv, set_key, dotenv_values

# 尝试导入 CORS（可选）
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False

from src.parser import DouyinLinkParser
from src.fetcher import DouyinFetcher
from src.asr_client import ASRClient
from src.local_asr_client import LocalASRClient
from config import Settings, ASR_PROVIDER_DASHSCOPE, ASR_PROVIDER_LOCAL

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 启用 CORS，允许跨域访问（用于外网访问）
if CORS_AVAILABLE:
    CORS(app, resources={r"/api/*": {"origins": "*"}})
else:
    print("⚠️  flask-cors 未安装，CORS 支持已禁用。如需跨域访问，请安装: uv add flask-cors")

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
        'ASR_PROVIDER': env_config.get('ASR_PROVIDER', current_settings.asr_provider),
        'DASHSCOPE_API_KEY': env_config.get('DASHSCOPE_API_KEY', current_settings.dashscope_api_key),
        'MAX_VIDEO_DURATION': env_config.get('MAX_VIDEO_DURATION', str(current_settings.max_video_duration)),
        'ASR_MODEL': env_config.get('ASR_MODEL', current_settings.asr_model),
        'OUTPUT_DIR': env_config.get('OUTPUT_DIR', str(current_settings.output_dir)),
        'OSS_ENABLE_FALLBACK': env_config.get('OSS_ENABLE_FALLBACK', str(current_settings.oss_enable_fallback).lower()),
        'OSS_ACCESS_KEY_ID': env_config.get('OSS_ACCESS_KEY_ID', current_settings.oss_access_key_id),
        'OSS_ACCESS_KEY_SECRET': env_config.get('OSS_ACCESS_KEY_SECRET', current_settings.oss_access_key_secret),
        'OSS_BUCKET_NAME': env_config.get('OSS_BUCKET_NAME', current_settings.oss_bucket_name),
        'OSS_ENDPOINT': env_config.get('OSS_ENDPOINT', current_settings.oss_endpoint),
    }
    # 隐藏 API Key 的显示（只显示前几位）
    api_key = config['DASHSCOPE_API_KEY']
    if api_key and len(api_key) > 10:
        masked_key = api_key[:10] + "..."
    else:
        masked_key = api_key if api_key else ""
    
    # 隐藏 OSS Secret
    oss_secret = config['OSS_ACCESS_KEY_SECRET']
    if oss_secret and len(oss_secret) > 10:
        config['OSS_ACCESS_KEY_SECRET_MASKED'] = oss_secret[:10] + "..."
    else:
        config['OSS_ACCESS_KEY_SECRET_MASKED'] = oss_secret if oss_secret else ""
    
    return render_template('config.html', config=config, masked_key=masked_key)


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置 API"""
    # 重新加载配置
    load_dotenv(ENV_FILE, override=True)
    current_settings = Settings()
    
    env_config = get_env_config()
    config = {
        'ASR_PROVIDER': env_config.get('ASR_PROVIDER', current_settings.asr_provider),
        'DASHSCOPE_API_KEY': env_config.get('DASHSCOPE_API_KEY', ''),
        'MAX_VIDEO_DURATION': env_config.get('MAX_VIDEO_DURATION', str(current_settings.max_video_duration)),
        'ASR_MODEL': env_config.get('ASR_MODEL', current_settings.asr_model),
        'OUTPUT_DIR': env_config.get('OUTPUT_DIR', str(current_settings.output_dir)),
        'OSS_ENABLE_FALLBACK': env_config.get('OSS_ENABLE_FALLBACK', str(current_settings.oss_enable_fallback).lower()),
        'OSS_ACCESS_KEY_ID': env_config.get('OSS_ACCESS_KEY_ID', current_settings.oss_access_key_id),
        'OSS_ACCESS_KEY_SECRET': env_config.get('OSS_ACCESS_KEY_SECRET', current_settings.oss_access_key_secret),
        'OSS_BUCKET_NAME': env_config.get('OSS_BUCKET_NAME', current_settings.oss_bucket_name),
        'OSS_ENDPOINT': env_config.get('OSS_ENDPOINT', current_settings.oss_endpoint),
    }
    # 隐藏敏感信息
    api_key = config['DASHSCOPE_API_KEY']
    if api_key and len(api_key) > 10:
        config['DASHSCOPE_API_KEY'] = api_key[:10] + "..."
    else:
        config['DASHSCOPE_API_KEY'] = api_key if api_key else ""
    
    oss_secret = config['OSS_ACCESS_KEY_SECRET']
    if oss_secret and len(oss_secret) > 10:
        config['OSS_ACCESS_KEY_SECRET'] = oss_secret[:10] + "..."
    else:
        config['OSS_ACCESS_KEY_SECRET'] = oss_secret if oss_secret else ""
    
    return jsonify({
        'success': True,
        'config': config
    })


@app.route('/api/config', methods=['POST'])
def save_config():
    """保存配置 API"""
    data = request.get_json()
    
    # 重新加载当前配置以获取默认值
    load_dotenv(ENV_FILE, override=True)
    current_settings = Settings()
    
    # 获取 ASR 提供商
    asr_provider = data.get('ASR_PROVIDER', current_settings.asr_provider).strip()
    
    # 验证必填字段：如果使用 DashScope，需要 API Key
    if asr_provider == 'dashscope':
        if 'DASHSCOPE_API_KEY' not in data or not data['DASHSCOPE_API_KEY'].strip():
            return jsonify({
                'success': False,
                'error': '使用 DashScope 时，DASHSCOPE_API_KEY 是必填项'
            }), 400
    
    # 验证 OSS 配置（如果启用）
    oss_enable = data.get('OSS_ENABLE_FALLBACK', 'false').strip().lower() == 'true'
    if oss_enable:
        required_oss_fields = ['OSS_ACCESS_KEY_ID', 'OSS_ACCESS_KEY_SECRET', 'OSS_BUCKET_NAME', 'OSS_ENDPOINT']
        for field in required_oss_fields:
            if not data.get(field) or not data.get(field).strip():
                return jsonify({
                    'success': False,
                    'error': f'启用 OSS 兜底方案时，{field} 是必填项'
                }), 400
    
    # 准备要保存的配置
    config_to_save = {
        'ASR_PROVIDER': asr_provider,
        'MAX_VIDEO_DURATION': data.get('MAX_VIDEO_DURATION', str(current_settings.max_video_duration)).strip(),
        'ASR_MODEL': data.get('ASR_MODEL', current_settings.asr_model).strip(),
        'OSS_ENABLE_FALLBACK': 'true' if oss_enable else 'false',
    }
    
    # DashScope 配置（如果使用）
    if asr_provider == 'dashscope' and data.get('DASHSCOPE_API_KEY'):
        dashscope_key = data['DASHSCOPE_API_KEY'].strip()
        # 如果是脱敏的值（包含...），需要从现有配置中获取完整值
        if not dashscope_key or dashscope_key.endswith('...'):
            # 尝试从现有配置中获取
            env_config = get_env_config()
            existing_key = env_config.get('DASHSCOPE_API_KEY', '')
            if existing_key and not existing_key.endswith('...'):
                config_to_save['DASHSCOPE_API_KEY'] = existing_key
            else:
                return jsonify({
                    'success': False,
                    'error': '请输入完整的 DashScope API Key'
                }), 400
        else:
            config_to_save['DASHSCOPE_API_KEY'] = dashscope_key
    elif asr_provider == 'local':
        # 本地模式，清空 DashScope API Key（可选）
        config_to_save['DASHSCOPE_API_KEY'] = ''
    
    # OSS 配置（如果启用）
    if oss_enable:
        # 检查 OSS Secret 是否被修改（不是脱敏的值）
        oss_secret = data.get('OSS_ACCESS_KEY_SECRET', '').strip()
        if oss_secret and oss_secret not in ['***已保存***', '...', '']:
            # 是新的完整值
            config_to_save['OSS_ACCESS_KEY_SECRET'] = oss_secret
        elif oss_secret in ['***已保存***', '...']:
            # 是脱敏的值，保留现有配置
            env_config = get_env_config()
            existing_secret = env_config.get('OSS_ACCESS_KEY_SECRET', '')
            if existing_secret and not existing_secret.endswith('...'):
                config_to_save['OSS_ACCESS_KEY_SECRET'] = existing_secret
            else:
                return jsonify({
                    'success': False,
                    'error': '请输入完整的 OSS AccessKey Secret'
                }), 400
        
        config_to_save['OSS_ACCESS_KEY_ID'] = data.get('OSS_ACCESS_KEY_ID', '').strip()
        config_to_save['OSS_BUCKET_NAME'] = data.get('OSS_BUCKET_NAME', '').strip()
        config_to_save['OSS_ENDPOINT'] = data.get('OSS_ENDPOINT', '').strip()
    else:
        # 未启用 OSS，清空相关配置
        config_to_save['OSS_ACCESS_KEY_ID'] = ''
        config_to_save['OSS_ACCESS_KEY_SECRET'] = ''
        config_to_save['OSS_BUCKET_NAME'] = ''
        config_to_save['OSS_ENDPOINT'] = ''
    
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


@app.route('/api/health', methods=['GET'])
def health():
    """Health check for container/orchestrator probes."""
    return jsonify({'ok': True})


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
        error_msg = '配置错误: '
        if current_settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
            error_msg += '未设置 DASHSCOPE_API_KEY，请先到配置页面设置'
        elif current_settings.asr_provider == ASR_PROVIDER_LOCAL:
            error_msg += 'Local Whisper 不可用，请检查是否已安装 Whisper'
        else:
            error_msg += f'未知的 ASR 提供商: {current_settings.asr_provider}'
        
        return jsonify({
            'success': False,
            'error': error_msg
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
        
        # 3. 语音识别（根据配置选择提供商）
        try:
            if current_settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
                # 使用 DashScope（云端）
                asr_client = ASRClient(current_settings.dashscope_api_key, current_settings.asr_model)
                text = asr_client.transcribe(video_url=metadata.video_url)
            elif current_settings.asr_provider == ASR_PROVIDER_LOCAL:
                # 使用 Local Whisper（本地）
                # 需要先下载视频并提取音频
                import tempfile
                from src.audio_processor import AudioProcessor
                
                # 检查 FFmpeg 是否安装
                audio_processor = AudioProcessor(
                    temp_dir=current_settings.temp_dir,
                    cleanup=False  # 手动清理
                )
                
                if not audio_processor.check_ffmpeg():
                    return jsonify({
                        'success': False,
                        'error': 'FFmpeg 未安装，无法提取音频。请先安装 FFmpeg 或使用 DashScope 云端服务'
                    }), 400
                
                # 创建临时文件路径
                video_path = current_settings.temp_dir / f"temp_video_{video_id}.mp4"
                audio_path = current_settings.temp_dir / f"temp_audio_{video_id}.wav"
                
                # 确保临时目录存在
                current_settings.temp_dir.mkdir(parents=True, exist_ok=True)
                
                # 下载视频文件
                downloaded_path = audio_processor.download_video(
                    video_url=metadata.video_url,
                    save_path=video_path
                )
                
                if not downloaded_path or not downloaded_path.exists():
                    return jsonify({
                        'success': False,
                        'error': '视频下载失败，请检查视频 URL 是否有效'
                    }), 500
                
                # 提取音频
                extracted_audio = audio_processor.extract_audio(
                    video_source=downloaded_path,
                    output_path=audio_path
                )
                
                if not extracted_audio or not extracted_audio.exists():
                    # 清理视频文件
                    if downloaded_path.exists():
                        try:
                            downloaded_path.unlink()
                        except Exception:
                            pass
                    return jsonify({
                        'success': False,
                        'error': '音频提取失败，请检查 FFmpeg 是否正确安装'
                    }), 500
                
                # 使用 Local Whisper 转写
                local_asr = LocalASRClient()
                text = local_asr.transcribe(audio_path=extracted_audio)
                
                # 清理临时文件
                if current_settings.cleanup_temp_files:
                    for temp_file in [downloaded_path, extracted_audio]:
                        if temp_file and temp_file.exists():
                            try:
                                temp_file.unlink()
                            except Exception:
                                pass
            else:
                return jsonify({
                    'success': False,
                    'error': f'未知的 ASR 提供商: {current_settings.asr_provider}'
                }), 400
            
            if not text:
                error_msg = '语音识别失败'
                if current_settings.asr_provider == ASR_PROVIDER_DASHSCOPE:
                    error_msg += '，请检查 API Key 是否有效'
                elif current_settings.asr_provider == ASR_PROVIDER_LOCAL:
                    error_msg += '，请检查 Whisper 是否正常工作'
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 500
        except ImportError as e:
            return jsonify({
                'success': False,
                'error': f'ASR 模块导入失败: {str(e)}'
            }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'语音识别过程出错: {str(e)}'
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


def get_local_ip() -> str:
    """获取本机局域网 IP 地址（优先返回实际局域网接口）"""
    try:
        # 方法1: 尝试通过连接外部地址获取
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        
        # 过滤掉虚拟接口和特殊 IP
        # 198.18.0.0/15 是文档和测试网络，不是实际局域网 IP
        if ip.startswith("198.18.") or ip.startswith("169.254."):
            # 如果获取到的是虚拟接口，尝试从系统获取实际 IP
            import platform
            if platform.system() == "Windows":
                try:
                    import subprocess
                    result = subprocess.run(
                        ["powershell", "-Command", 
                         "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' -and $_.IPAddress -notlike '198.18.*' -and $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*WSL*' } | Select-Object -First 1 -ExpandProperty IPAddress"],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        ip = result.stdout.strip()
                except Exception:
                    pass
        
        return ip
    except Exception:
        # 方法2: 如果失败，返回 localhost
        return "localhost"


if __name__ == '__main__':
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
        print(f"🌍 外网访问: 需要配置端口转发或使用公网 IP")
        print(f"")
        print(f"⚠️  重要提示:")
        print(f"   - 确保使用正确的 IP 地址: {local_ip}")
        print(f"   - 如果无法访问，请检查防火墙设置")
        print(f"   - 运行防火墙脚本: scripts\\open_firewall_port.ps1 {port}")
    else:
        print(f"⚠️  仅监听 {host}，可能无法外网访问")
    print(f"⚙️  调试模式: {'开启' if debug else '关闭'}")
    print("=" * 70)
    print("💡 提示: 按 Ctrl+C 停止服务")
    print("=" * 70)
    print()
    
    # 确保监听所有接口
    if host != '0.0.0.0':
        print(f"⚠️  警告: host={host}，建议使用 0.0.0.0 以允许局域网访问")
        print()
    
    app.run(debug=debug, host=host, port=port, threaded=True)
