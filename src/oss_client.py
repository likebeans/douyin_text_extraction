"""阿里云 OSS 客户端模块

用于上传音频文件到 OSS，获取公网 URL 供 DashScope 使用
"""
import oss2
from pathlib import Path
from typing import Optional
from datetime import datetime
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
        cdn_domain: Optional[str] = None
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
        
        # 创建认证对象
        auth = oss2.Auth(access_key_id, access_key_secret)
        
        # 创建 Bucket 对象（优先使用内网 Endpoint，如果配置了的话）
        # 注意：内网 Endpoint 只能在同地域的 ECS 上使用，外网访问必须用外网 Endpoint
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
    
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
                remote_path = f"douyin_audio/{timestamp}_{local_file.name}"
            
            # 上传文件
            console.print(f"[dim]   本地文件: {local_file}[/dim]")
            console.print(f"[dim]   OSS 路径: {remote_path}[/dim]")
            
            with open(local_file, 'rb') as f:
                result = self.bucket.put_object(remote_path, f)
            
            if result.status != 200:
                console.print(f"[red]❌ 上传失败，状态码: {result.status}[/red]")
                return None
            
            # 生成公网访问 URL
            # 优先使用 CDN 域名（如果配置了），否则使用外网 Endpoint
            if self.cdn_domain:
                # 使用 CDN 域名（需要确保 CDN 已配置并指向 OSS）
                cdn_clean = self.cdn_domain.replace('http://', '').replace('https://', '')
                public_url = f"https://{cdn_clean}/{remote_path}"
            else:
                # 使用外网 Endpoint
                endpoint_clean = self.endpoint.replace('http://', '').replace('https://', '')
                public_url = f"https://{self.bucket_name}.{endpoint_clean}/{remote_path}"
            
            console.print(f"[green]✅ 上传成功[/green]")
            console.print(f"[dim]   公网 URL: {public_url[:80]}...[/dim]")
            
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
