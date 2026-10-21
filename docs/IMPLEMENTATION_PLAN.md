# 实施计划

固定流程：Parser → Classifier → Extractor → Analyzer → Summarizer → Validator → Exporter。
默认仅本机 Mock，Python 3.10+；不需要 GPU、模型下载或 API Key。

| 阶段 | 交付 | 完成条件 |
|---|---|---|
| V0 | pyproject、domain/schema、文本 Parser、fixture Mock、Pipeline、CLI | 离线 JD JSON/Markdown、基础 pytest 和 Ruff 通过，独立提交 |
| V1 | PDF/API、版本化 prompts、兼容 API、有限修复、证据、长文 Map/Reduce、缓存与用量 | 正常输入与关键错误恢复测试通过，独立提交 |
| V2 | 40 条自建标注样例、评测器、完整测试、CI、Docker、Makefile | 生成 JSON/CSV/Markdown 评测，快速开始可复现，独立提交 |
| V3 | 中文展示文档、英文 Overview、隐私检查、公开 GitHub 发布 | 检查记录真实，测试通过，确认账户与目录后普通推送，复核远端 |

目录：`app/{domain,services,adapters,infra}`、`schema/`、`prompts/`、`examples/`、`eval/`、`tests/`、`docs/`。
各阶段保留可运行入口 `python -m app.cli analyze examples/jd.txt --output outputs/jd.json`。

## 环境预检（2026-10-21，Asia/Shanghai）

- `pwd` 与 `realpath .`：项目父工作区一致；父目录不是 Git 仓库，目标目录原先不存在。
- `uname -s`: Linux；Python 3.12.3；Git 2.43.0；gh 2.45.0；Docker 29.8.2；Node v24.21.0。
- `gh auth status` 与 `gh api user --jq .login`：已登录 FouHe0720；目标远程仓库尚不存在。
- Docker daemon 可用。不会修改兄弟项目。
- 所有依赖安装到项目 `.venv`；真实 API 调用需用户自行配置，当前不使用任何密钥。
