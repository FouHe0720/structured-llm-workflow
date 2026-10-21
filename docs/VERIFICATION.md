# 本机验证记录

日期：2026-10-21，Asia/Shanghai。结果来自实际执行命令。

## 环境与隔离

- 初始系统 Python 3.12.3 缺少 ensurepip；使用已安装的 uv 建立项目 `.venv`，实际解释器为 Python 3.12.15。
- Git 2.43.0、gh 2.45.0、Docker daemon 29.8.2；WSL 中 gh 账户确认是 FouHe0720。
- 父工作区不是 Git 仓库，只在新建目标项目初始化 Git；没有修改兄弟项目。
- 未执行 sudo、全局 pip 安装、模型下载、GPU 训练或外部真实模型调用。

## 已通过命令

| 命令/验证 | 实际结果 |
|---|---|
| `make install` | `uv sync --extra dev --frozen` 成功 |
| `make check` | Ruff lint/format 通过；pytest 60 passed |
| `make demo` | JD、PDF、50K 字符 JSON 与 Markdown 成功 |
| 全类型 CLI | paper / meeting / report / injection / conflict 示例可运行 |
| 1K / 10K / 50K 集成测试 | 全部原文切片可还原，尾部字段保留；长文调用包含 Reduce |
| `python -m eval.run_eval --output eval/results/mock` | 40 条完成；机器可读结果已提交 |
| `uv build` | sdist / wheel 成功，wheel 含 9 个 prompt 和 Mock JSON fixture |
| 实际本机 uvicorn HTTP | health=200；analyze=200 / job_description / passed |
| 真实 localhost fixture endpoint | OpenAI-compatible adapter 经真实 socket 完成四步调用；不是真实 LLM |
| `docker build -t structured-llm-workflow:local .` | 构建成功，依赖按带 hash lock 安装 |
| 容器外工作目录 CLI | 在 /tmp 工作目录调用已安装包，JD 报告成功，验证非仅源码导入 |
| 容器 HTTP / user | health=200；analyze=200；UID=10001；验证后移除本次临时容器 |
| `python -m scripts.check_public` | 通过，未匹配凭据、机器绝对路径、私网 endpoint 或私钥模式 |

pytest 有一条 `StarletteDeprecationWarning`：当前 Starlette 的 TestClient 提示 httpx 兼容层将被弃用，
建议 httpx2。没有压制这条 warning；生产 adapter 明确依赖 httpx 0.28，测试仍可运行。

## 评测快照与解释

以 `eval/results/mock/results.json` 中 generated_at、Python、prompt_version 与 dataset_sha256 为准：

- 文档 40；schema 合法报告 37/40；gold 字段正确 180/192。
- 类型正确 36/40；最终报告无原文 span 支持断言 0/141。
- 无支持断言的修复前/拒绝尝试 2 次；总 Mock 调用 329 次。
- 满足完整预期 39/40；1 条刻意错分被 evaluator 检出。
- 三条预期拒绝：`mm08` 超时、`un07` 无支持断言、`un08` JSON 修复耗尽。
- P50/P95 取已提交 JSON，约 3.08/3.83 ms；运行会有波动，不能外推真实模型性能。

gold 字段为本项目逐条显式编写，未获独立人工复核；分母定义见 `eval/README.md`。
所有 Mock 故障在数据中公开，不偷偷删掉失败案例。`--require-expectations` 对这套故障集预期非零。

## 网络与 CI 的边界

- Python 依赖下载、Docker base/依赖下载真实执行过；完整离线工作流在安装后不需要网络。
- 外部真实 LLM：未配置、未调用；不得引用本仓库 Mock 结果宣称真实模型准确率。
- CI 配置包含 Python 3.10 / 3.12 与 Docker job。远端运行由发布后的 Actions 触发，
  以仓库顶部 badge 和 Actions 运行记录为准；本文件的 60 passed 指本机 Python 3.12。
- 自建价格表默认空；本次 cost=null，没有使用或推断商业实时价格。

## 公开发布检查

仅跟踪代码、锁文件、原创示例/标注和评测快照；`.env`、`.venv`、数据库、日志、
运行时 outputs、缓存、下载与模型权重被忽略。项目扫描是针对本仓库的有限规则，不能替代专业 secret scanner。
发布前再次核对工作目录 / Git 根目录、账户、staged 文件、远端归属和 PUBLIC 设置；不强推、不覆盖其他仓库。
