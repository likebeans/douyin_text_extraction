# 贡献指南

感谢你愿意为 douyin-text-extractor 提交改进。提交前请先查看现有 Issues，避免重复工作；较大的功能改动可以先开 Issue 讨论。

## 开发环境

需要 Python 3.10 或更新版本，以及 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/likebeans/douyin_text_extraction.git
cd douyin_text_extraction
uv sync --locked --all-groups
```

本机 Whisper 相关改动还需要安装可选依赖：

```bash
uv sync --locked --all-groups --extra local
```

## 代码与提交

- 保持改动聚焦，避免把访问令牌、API Key、OSS 凭据、`.env`、真实个人数据或生成的大文件加入提交。
- 对外行为变化应同步更新 README 或 `docs/` 中相关说明。
- 使用清晰的提交标题说明改动目的。

## 验证

默认测试完全离线运行，不会调用抖音、DashScope 或 OSS：

```bash
uv run --locked pytest
```

打包与入口检查：

```bash
uv build --wheel --no-sources
python -m zipfile -l dist/douyin_text_extractor-1.0.0-py3-none-any.whl
uv run douyin-extract --help
uv run python -c 'from web_app import app; client=app.test_client(); assert client.get("/").status_code == 200; assert client.get("/static/style.css").status_code == 200'
```

需要使用真实 OSS 的集成测试必须显式启用；它可能创建和删除云端对象并产生费用：

```bash
uv run pytest --run-integration -m integration
```

只有在明确设置了专用测试 Bucket 凭据并接受远端副作用时才运行集成测试。普通测试不会因本机存在凭据而访问远端服务。

## Pull request

请在 PR 中说明改动、用户可观察到的行为变化、执行过的离线验证，以及尚未覆盖的边界。不要在 PR 描述中粘贴密钥或令牌。
