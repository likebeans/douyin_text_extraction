# 更新日志

## 未发布

本次优化保留当前包版本 `0.3.0`，以下变更尚未发布为 GitHub Release。

- 规范化包元数据、MIT 许可、CLI/Web 命令入口与 wheel 资源清单。
- 将 Whisper 作为可选依赖，默认安装避免引入大型机器学习依赖。
- Web API 支持 Bearer 或 `X-API-Token` 认证；健康检查 `/api/health` 不要求令牌。
- Web API 提取为同步请求；长转写期间客户端需等待响应，超出并发上限时返回 429，不提供进度查询。
- OSS 默认使用限时签名 URL 支持私有 Bucket；详见 [OSS 配置指南](docs/OSS_GUIDE.md)。
- 新增独立的 `FFMPEG_TIMEOUT` 和经令牌保护的 `WEB_PUBLIC_ORIGIN` 配置说明；媒体下载的初始 URL 与重定向目标受平台/CDN 域名校验。
- 默认测试不连接外部服务；真实 OSS 测试须显式启用。
- 修复分享页 HTTP 200 但间歇性缺失视频详情的情况，复用会话进行有限重试并区分无视频、访问拒绝和数据异常。
- 新增 `DOWNLOAD_TIMEOUT=300`，将媒体下载总时限与 `REQUEST_TIMEOUT` 的连接/读取等待超时分开，避免持续下载的视频被 30 秒时限中断。
- 补充抖音冷媒体节点 `idouyinvod.com` 的域名校验支持，修复部分精选视频重定向到该 CDN 后被误拒绝的问题。
