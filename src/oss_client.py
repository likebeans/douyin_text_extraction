"""阿里云 OSS 客户端模块

用于上传音频文件到 OSS，获取公网 URL 供 DashScope 使用
"""
import oss2
from pathlib import Path
from typing import Optional
from datetime import datetime
from urllib.parse import quote, urlsplit
from uuid import uuid4
from rich.console import Console

console = Console()


class OSSClient:
    """阿里云 OSS 客户端
    
    用于上传音频文件到 OSS，获取公网 URL 供 DashScope 使用
    
    使用场景：
    - DashScope 直接 URL 转写失败时的兜底方案
    - 将本地音频文件上传到 OSS，获得公网可访问的 URL
    
    成本：
    - 存储：¥0.00012/GB/小时
    - 流量：¥0.5/GB
    - 单个 5MB 文件成本 < ¥0.003
    """
    
    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        endpoint: str,
        endpoint_internal: Optional[str] = None,
        cdn_domain: Optional[str] = None,
        request_timeout: int = 30,
        sign_url_expires: int = 3600,
    ):
        """初始化 OSS 客户端
        
        Args:
            access_key_id: 阿里云 AccessKey ID
            access_key_secret: 阿里云 AccessKey Secret
            bucket_name: OSS Bucket 名称
            endpoint: OSS 外网 Endpoint（如：oss-cn-wuhan-lr.aliyuncs.com）
            endpoint_internal: OSS 内网 Endpoint（可选，同地域访问更快更便宜）
            cdn_domain: CDN 加速域名（可选，用于加速访问）
        """
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.endpoint_internal = endpoint_internal
        self.cdn_domain = cdn_domain
        self._cdn_url = self._https_endpoint(cdn_domain) if cdn_domain else None

        self.sign_url_expires = sign_url_expires
        auth = oss2.Auth(access_key_id, access_key_secret)
        external_endpoint = self._https_endpoint(endpoint)
        transfer_endpoint = self._https_endpoint(endpoint_internal) if endpoint_internal else external_endpoint
        self.bucket = oss2.Bucket(auth, transfer_endpoint, bucket_name, connect_timeout=request_timeout)
        # 签名使用公网 Endpoint，避免向 DashScope 提交仅内网可访问的地址。
        self.public_bucket = (
            self.bucket if transfer_endpoint == external_endpoint
            else oss2.Bucket(auth, external_endpoint, bucket_name, connect_timeout=request_timeout)
        )

    @staticmethod
    def _https_endpoint(value: str) -> str:
        parsed = urlsplit(value if "://" in value else f"https://{value}")
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise ValueError("OSS Endpoint/CDN 必须是有效的 HTTPS 主机地址")
        return f"https://{parsed.netloc}"
    
    def upload_audio(
        self,
        local_file: Path,
        remote_path: Optional[str] = None
    ) -> Optional[tuple[str, str]]:
        """上传音频文件到 OSS
        
        Args:
            local_file: 本地音频文件路径
            remote_path: OSS 中的存储路径（不指定则自动生成）
            
        Returns:
            (公网访问 URL, OSS 路径) 元组，失败返回 None
        """
        console.print("[cyan]📤 上传音频到 OSS...[/cyan]")
        
        if not local_file.exists():
            console.print(f"[red]❌ 本地文件不存在: {local_file}[/red]")
            return None
        
        try:
            # 生成远程路径（使用时间戳避免冲突）
            if not remote_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                remote_path = f"douyin_audio/{timestamp}_{uuid4().hex}{local_file.suffix}"
            
            # 上传文件
            console.print(f"[dim]   本地文件: {local_file}[/dim]")
            console.print(f"[dim]   OSS 路径: {remote_path}[/dim]")
            
            with open(local_file, 'rb') as f:
                result = self.bucket.put_object(remote_path, f)
            
            if result.status != 200:
                console.print(f"[red]❌ 上传失败，状态码: {result.status}[/red]")
                return None
            
            if self.cdn_domain:
                # 自定义 CDN 需要部署者配置回源权限；不把 OSS 签名套用到 CDN。
                public_url = f"{self._cdn_url}/{quote(remote_path, safe='/')}"
            else:
                # 临时签名允许私有 Bucket，不要求把上传的音频设为公共可读。
                public_url = self.public_bucket.sign_url('GET', remote_path, self.sign_url_expires)

            console.print("[green]✅ 上传成功[/green]")
            
            return (public_url, remote_path)
            
        except oss2.exceptions.OssError as e:
            console.print(f"[red]❌ OSS 错误: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ 上传失败: {e}[/red]")
            return None
    
    def delete_file(self, remote_path: str) -> bool:
        """删除 OSS 文件
        
        Args:
            remote_path: OSS 文件路径
            
        Returns:
            是否删除成功
        """
        try:
            self.bucket.delete_object(remote_path)
            console.print(f"[dim]>> 已删除 OSS 文件: {remote_path}[/dim]")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠ 删除 OSS 文件失败: {e}[/yellow]")
            return False
    
    def test_connection(self) -> bool:
        """测试 OSS 连接是否正常
        
        Returns:
            连接是否正常
        """
        try:
            # 尝试列出 bucket 信息
            self.bucket.get_bucket_info()
            return True
        except Exception as e:
            console.print(f"[red]❌ OSS 连接失败: {e}[/red]")
            return False
