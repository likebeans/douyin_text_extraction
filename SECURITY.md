# 安全问题报告

请勿在公开 Issue、讨论区或 Pull Request 中报告尚未修复的安全问题，也不要粘贴任何 API Key、OSS AccessKey、访问令牌或个人数据。

仓库启用 GitHub 私密漏洞报告后，可通过 [Security → Report a vulnerability](https://github.com/likebeans/douyin_text_extraction/security/advisories/new) 提交报告。若该入口不可用，请先创建仅请求私密联系渠道的 Issue，不要公开漏洞细节、复现步骤或凭据。

请尽量说明受影响的版本、部署方式、影响范围和可安全复现问题所需的信息。报告中请移除真实凭据和用户内容。

## 部署提示

远程访问 Web API 时请设置高熵 `WEB_API_TOKEN`，并通过 HTTPS 反向代理访问。不要把 API 令牌放入 URL、前端代码、日志或公开截图。Compose 默认只向本机发布端口；如要调整网络暴露范围，请先配置 TLS 终止、访问控制和防火墙。
