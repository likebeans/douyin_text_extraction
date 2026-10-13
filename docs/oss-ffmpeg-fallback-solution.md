---
planStatus:
  title: OSS + FFmpeg 备用流程（历史设计记录）
  status: historical
  planType: documentation
  tags:
    - oss
    - ffmpeg
---

# OSS + FFmpeg 备用流程（历史设计记录）

> 本文档保留早期方案背景。旧版成功率、准确率、性能、成本目标和代码片段不是当前行为或经验证指标。当前配置与实现请查看[OSS 配置指南](OSS_GUIDE.md)。

当前实现可在 DashScope 直接 URL 转写失败后，按需使用 FFmpeg 提取音频、上传到已配置的 OSS Bucket 并继续转写。默认情况下该备用流程关闭。上传 URL、Bucket 访问控制和费用取决于用户的 OSS、CDN 与 DashScope 配置。

离线测试不会向 OSS 上传数据；可能产生远端副作用的集成测试必须通过 `--run-integration` 显式启用。