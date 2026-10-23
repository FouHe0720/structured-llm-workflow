# 使用手册

本手册覆盖安装、离线分析、校园审阅、HTTP 接口、模型配置和实现结构。
所有命令默认从仓库根目录执行；示例使用 Bash，Python 命令指向项目自己的 `.venv`。

## 1. 功能与适用范围

本项目把文档转换成带原文证据的结构化报告。
处理步骤固定，模型不会选择工具，也不会执行文档中的指令。

| 功能 | 入口 | 输出 |
|---|---|---|
| 文本、Markdown、文本型 PDF 分析 | 通用 CLI、HTTP | AnalysisReport |
| 六类文档 Schema | 分类与提取阶段 | 类型匹配的 extracted |
| 原文支持检查 | 每次调用与最终校验 | quote、段落、页码、字符偏移 |
| 长文处理 | Pipeline | 全文分块、合并、分层摘要 |
| 冲突保留 | 合并与分析阶段 | 冲突候选；对应标量置空 |
| 历史招生资料审阅 | `python -m app.campus` | JSON 审阅包、Markdown 审阅单 |
| 兼容模型接口 | Provider adapter | 经同样校验的模型结果 |
| 缓存、用量与价格 | 基础设施层 | 命中记录、token 来源、可空费用 |
| 固定样例评测 | `python -m eval.run_eval` | JSON、CSV、Markdown |

默认使用确定性 Mock，不需要 GPU、模型下载或 API Key。
Mock 根据字段标签与已知招生段落匹配，不是通用自然语言理解模型。
PDF 只提取已有文本，不提供 OCR、版面重建或表格结构恢复。
API 没有用户系统、任务队列、认证、用户级限流或历史报告查询。

## 2. 环境与安装

需要 Python 3.10+；Linux / WSL 可直接使用 Makefile。
Docker 是可选运行方式，CLI 与 API 本身不依赖 Docker。
首次安装需要访问 Python 包索引，安装完成后的 Mock 分析可离线运行。

```bash
python3 --version
make install
.venv/bin/python -m app.cli --help
```

`make install` 优先执行 `uv sync --extra dev --frozen`，按 `uv.lock` 安装。
没有 uv 时，会创建 `.venv` 并通过 pip 按项目依赖范围安装：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

若创建 venv 时缺少 `ensurepip`，需先安装系统对应的 venv 支持，或使用已有 uv。
不要把包安装到系统 Python，也不需要下载模型权重。
生产依赖的带哈希清单位于 `requirements.lock`，Docker 构建使用它。

## 3. 第一次离线分析

先创建专用的临时输出目录，避免覆盖已有报告：

```bash
workflow_demo_dir=$(mktemp -d)
WORKFLOW_PROVIDER=mock .venv/bin/python -m app.cli analyze examples/jd.txt \
  --output "$workflow_demo_dir/jd.json"
cat "$workflow_demo_dir/jd.md"
```

成功时命令退出码为 0，stdout 给出类型、输出路径和 `passed`。
同时生成 `jd.json` 与 `jd.md`；源文件不被修改。
错误时退出码为 1，stderr 返回结构化错误，不写成“成功报告”。

也可以使用安装后的命令名：

```bash
.venv/bin/document-workflow analyze examples/meeting.txt \
  --output "$workflow_demo_dir/meeting.json"
```

报告路径必须以 `.json` 结尾；相邻 `.md` 路径也不能与输入路径相同。
导出使用临时文件与原子替换，但 JSON、Markdown 两个文件之间没有跨文件事务。
已有同名输出会被替换；需要保留版本时使用不同输出目录。

### 3.1 通用 CLI 的全部参数

```text
python -m app.cli [-h] analyze [-h] [--output OUTPUT] input
```

| 参数 | 默认值 | 含义 |
|---|---|---|
| `input` | 必填 | `.txt`、`.md` 或文本型 `.pdf` 文件 |
| `--output` | `outputs/report.json` | JSON 路径，同时生成同名 Markdown |
| `-h` / `--help` | — | 顶层或子命令帮助 |

`document-workflow` 与 `python -m app.cli` 使用同一个入口。
目前只有 `analyze` 子命令，没有目录批处理、文件监控或报告删除命令。

### 3.2 PDF、长文和冲突示例

```bash
.venv/bin/python -m app.cli analyze examples/sample.pdf \
  --output "$workflow_demo_dir/pdf.json"
.venv/bin/python -m app.cli analyze examples/long_50000.txt \
  --output "$workflow_demo_dir/long.json"
.venv/bin/python -m app.cli analyze examples/conflict.txt \
  --output "$workflow_demo_dir/conflict.json"
```

长文报告里的 `metadata.chunks` 与 `warnings` 说明实际分块情况。
超过预算的单行会被拆开；程序不静默丢弃尾部，但跨块关系可能丢失。
冲突报告保留 `conflicts[].values`，受影响的标量字段设为 `null`。

`make demo` 会重新生成示例文件，并向 `outputs/` 写入 JD、PDF 和长文报告。
需要隔离运行产物时，使用上面的单文件命令。

## 4. 校园招生资料审阅

内置两份山东大学（威海）历史招生材料，共 20 个原文段落：

- `navigation-admission-2024`：智能导航特色班。
- `computational-law-admission-2024`：计算法学实验班。

资料位于 `app/fixtures/campus/`，随 Python 包一起安装。
原始 DOCX 不随仓库分发；来源清单保存原文件相对路径、哈希、年份、年级和段落。
它们是 2024 年资料，不代表当前招生安排。

```bash
.venv/bin/python -m app.campus \
  --source-id navigation-admission-2024 \
  --as-of 2026-10-23 \
  --output "$workflow_demo_dir/navigation.json"
.venv/bin/python -m app.campus \
  --source-id computational-law-admission-2024 \
  --as-of 2026-10-23 \
  --output "$workflow_demo_dir/law.json"
```

`--as-of` 是显式审阅日期，格式为 `YYYY-MM-DD`。
这里固定日期，方便重复检查历史资料规则；使用时可传入实际审阅日期。

| 参数 | 默认值 | 含义 |
|---|---|---|
| `--manifest` | 包内 `fixtures/campus/manifest.json` | 来源清单 |
| `--source-id` | `navigation-admission-2024` | 清单中唯一资料 ID |
| `--as-of` | 必填 | 用于资料年份检查的审阅日期 |
| `--output` | `outputs/campus-review.json` | 审阅 JSON 及同名 Markdown |
| `-h` / `--help` | — | 查看帮助 |

程序从 manifest 所在目录读取 `file_name` 对应的摘录。
摘录哈希与报告哈希不一致时拒绝生成审阅包。
输出不能覆盖 manifest，也不能覆盖清单中的任何来源文件。

### 4.1 审阅包怎么看

- `status` 始终为 `needs_human_review`，没有自动批准或发布功能。
- `source` 保存来源信息与原文件、摘录哈希。
- `report` 是完整通用 AnalysisReport。
- `evidence` 增加 `source_paragraph`，可回到原 DOCX 段落。
- `issues` 记录缺项、时间歧义、年份与名额冲突。

Markdown 先显示需要核对的问题，再列报名对象、报名时间和选拔规则。
原文证据去重后折叠展示，来源记录与文件指纹可以展开。

智能导航原文中的“9月9日中午14点”会保留，并标记 `ambiguous_time`。
计算法学报名时间没有显式年份时，标记 `year_not_explicit`，不自动补全。
招生名额与面试入围比例分别保留；不同名额数字会触发 `conflicting_quota`。
这套规则不判断个人资格，也不是完整的自然语言日期解析器。

## 5. 启动 HTTP 服务

默认启动方式监听 `127.0.0.1:8000`：

```bash
make serve
# 等价：.venv/bin/python -m app.api
```

多个项目同时运行时，本项目统一使用 **8102**：

```bash
WORKFLOW_PROVIDER=mock .venv/bin/python -m uvicorn app.api:create_app \
  --factory --host 127.0.0.1 --port 8102
```

端口由 uvicorn 参数指定，没有 `WORKFLOW_PORT` 环境变量。
只运行一个启动命令，在另一个终端执行下文请求；结束时按 `Ctrl+C`。
下文 curl 使用 8102；若选择默认启动方式，请将请求中的端口改为 8000。
新终端仍须位于仓库根目录，并重新创建自己的响应目录：

```bash
workflow_demo_dir=$(mktemp -d)
```

| 项目 | 多项目运行时的端口 |
|---|---|
| llm-gateway-service | 8101 |
| structured-llm-workflow | 8102 |
| rag-knowledge-engine | 8103 |
| workspace-agent | CLI / stdio，无 HTTP 端口 |
| agentops-eval-platform | 8105 |
| deep-research-agent | 8106 |

### 5.1 全部 HTTP 路由

| 方法 | 路径 | 请求 / 返回 |
|---|---|---|
| GET | `/health` | 存活信息、provider、model；不探测模型服务 |
| POST | `/v1/analyze` | 严格 JSON 输入，返回 AnalysisReport |
| POST | `/v1/analyze/file` | multipart 字段 `file`，返回 AnalysisReport |
| GET | `/openapi.json` | 实际 OpenAPI Schema |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc 文档 |
| GET | `/docs/oauth2-redirect` | FastAPI 文档 UI 的辅助页面，不代表实现 OAuth 认证 |

没有单独的校园审阅 HTTP 路由。
API 能识别 `campus_admission`，但来源匹配和审阅业务规则由校园 CLI 额外执行。

### 5.2 健康检查与文本请求

```bash
curl -fsS http://127.0.0.1:8102/health
curl -fsS http://127.0.0.1:8102/v1/analyze \
  -H 'Content-Type: application/json' \
  --data-binary '{"text":"Job Description\nPosition: Reviewer\nSkills: Python\nSummary: Review source evidence.","name":"reviewer.txt"}'
```

JSON 请求只有以下两个字段，其他字段被拒绝：

| 字段 | 类型 | 规则 |
|---|---|---|
| `text` | string，必填 | Schema 长度 1–1,000,000；还受配置字节、字符上限约束 |
| `name` | string | 默认 `input.txt`，长度 1–100；用于报告元数据 |

空白正文、NUL 字符、非字符串值和无效 JSON 都不能作为正常文档处理。
JSON 路由直接解析正文；`name` 不触发服务器读取本地同名文件。

### 5.3 文件上传与保存响应

```bash
curl -fsS http://127.0.0.1:8102/v1/analyze/file \
  -F 'file=@examples/sample.pdf' > "$workflow_demo_dir/http-pdf.json"
curl -fsS http://127.0.0.1:8102/v1/analyze/file \
  -F 'file=@app/fixtures/campus/navigation-admission-2024.md' \
  > "$workflow_demo_dir/http-campus.json"
```

HTTP 只返回 JSON，不自动把报告写入服务器磁盘；重定向由调用方保存文件。
上传字段名必须为 `file`，扩展名限 `.txt`、`.md`、`.pdf`。
纯文本按 UTF-8 读取，允许 UTF-8 BOM；PDF 保留一基页码。

### 5.4 错误返回

```json
{
  "error": {
    "code": "unsupported_type",
    "message": "Supported extensions: .txt, .md, .pdf",
    "step": "parser",
    "partial": {}
  }
}
```

| HTTP 状态 | 典型情况 |
|---|---|
| 413 | 请求体、文件、文本或 PDF 页数超限 |
| 422 | 输入 Schema、解析或校验失败；不存在的路由通常为 404 |
| 502 | 模型协议、模型输出、预算或其他非 parser/validator 阶段错误 |
| 504 | `llm_timeout` |

请求 Schema 错误只返回安全的 `invalid_request`，不回显完整输入。
模型服务的错误正文不会直接转发；上游 401、429 等不原样变成本服务的 HTTP 状态。

## 6. AnalysisReport 字段与 Schema

| 字段 | 内容 |
|---|---|
| `type` | 六种文档类型之一 |
| `metadata` | 文件名、文本哈希、字符数、页数、分块数 |
| `extracted` | 与类型严格匹配的提取模型 |
| `summary` | 抽取式摘要 |
| `risks_or_highlights` | 原文支持的风险与亮点 |
| `evidence` | 字段、引文、页码、段落、`start`、`end` |
| `conflicts` | 标量字段与全部冲突候选 |
| `model_info` | provider、模型、提示词版本、输出模式 |
| `timings` | 解析及各步骤耗时，单位毫秒 |
| `usage` | 调用数、缓存、token 来源、费用及逐次记录 |
| `validation_status` | 成功报告为 `passed` |
| `warnings` | Mock、分块、PDF 或冲突相关说明 |

| type | extracted 字段 |
|---|---|
| `job_description` | position、skills、experience、responsibilities、summary |
| `paper_abstract` | title、authors、objective、method、findings、summary |
| `meeting_minutes` | title、date、participants、decisions、action_items、summary |
| `technical_report` | title、system、metrics、limitations、recommendations、summary |
| `campus_admission` | title、audience、registration_window、quota_rules、selection_rules、restrictions、summary |
| `unknown` | summary |

所有模型禁止额外字段，采用严格类型。
缺失事实保持 `null` 或空列表，不推测作者、年限、指标或日期。
`start:end` 是解析后文本的 Unicode 字符偏移，end 不包含在片段内。
它不是 PDF 字节位置或页面坐标；重复引文定位到首次出现的位置。
文本文件 `pages=0`，证据页码为 `null`；PDF 页码从 1 开始。

## 7. 接入真实模型

只在需要调用外部服务时设置 provider。
接口须兼容非流式 Chat Completions 的文本返回；base URL 后会追加 `/chat/completions`。

```bash
cp .env.example .env
# 编辑 .env，保留为本机私人配置。
```

最小配置示意：

```dotenv
WORKFLOW_PROVIDER=openai
WORKFLOW_MODEL=your-provider-model
WORKFLOW_BASE_URL=https://provider.example/v1
WORKFLOW_API_KEY=
WORKFLOW_RESPONSE_MODE=json_schema
```

这里的地址、模型名是占位值，自建无认证服务可以留空 Key。
Settings 会读取当前目录的 `.env`，进程环境变量可覆盖它。
如果服务不支持 JSON Schema，手动改为 `json_object`；仍不支持时选择 `text`。
不会把认证失败、超时或任意 400 自动解释成能力降级。

```bash
.venv/bin/python -m scripts.smoke_real
```

此命令会调用配置的真实服务，并写 `outputs/real-smoke.json` 与同名 Markdown。
它不接受自定义输出参数；需要隔离输出时使用通用 CLI 的 `--output`。
真实模型结果仍需经过 JSON、Pydantic 和原文支持检查。
本手册的验证没有运行真实模型，也不提供模型质量或费用承诺。

## 8. 全部 WORKFLOW 配置

参数来自 `app/infra/config.py`；环境变量统一为 `WORKFLOW_` 前缀。
相对路径以进程工作目录为基准，启动 CLI/API 前应确认所在目录。

| 环境变量 | 默认值 | 范围与作用 |
|---|---|---|
| `WORKFLOW_PROVIDER` | `mock` | `mock` / `openai` |
| `WORKFLOW_MODEL` | `mock-fixture-v1` | 真实模式必须改为服务支持的非空模型名 |
| `WORKFLOW_BASE_URL` | 空 | 真实模式须为 HTTP(S) URL，无内嵌凭据、query、fragment |
| `WORKFLOW_API_KEY` | 空 | 可选 Bearer 凭据，不放入公开文件 |
| `WORKFLOW_RESPONSE_MODE` | `json_schema` | `json_schema` / `json_object` / `text` |
| `WORKFLOW_TIMEOUT_SECONDS` | 30 | 0.01–300 秒，单次 HTTP 调用超时 |
| `WORKFLOW_MAX_REPAIRS` | 1 | 0–2，结构或原文支持错误的修复次数 |
| `WORKFLOW_MAX_BYTES` | 2097152 | 100–10485760，文本/文件字节上限 |
| `WORKFLOW_MAX_CHARS` | 200000 | 100–1000000，解析后字符上限 |
| `WORKFLOW_MAX_PAGES` | 50 | 1–200，PDF 页数上限 |
| `WORKFLOW_CHUNK_TOKENS` | 1200 | 256–16000，源分块的 UTF-8 字节估算预算 |
| `WORKFLOW_MAX_CALLS` | 512 | 4–4096，每份文档的非缓存模型调用上限 |
| `WORKFLOW_CONTEXT_TOKENS` | 8192 | 4096–1000000，提示词、Schema、源文及输出预留总估算 |
| `WORKFLOW_CACHE_ENABLED` | false | 是否写本机结果缓存 |
| `WORKFLOW_CACHE_DIR` | `.cache/workflow` | 本地缓存目录 |
| `WORKFLOW_PRICE_FILE` | `config/prices.json` | 可选价格表 |

ASGI 请求体另允许 `MAX_BYTES + 65536` 字节，给 JSON/multipart 格式留出有限开销。
实际文本/文件仍单独检查，不因额外格式空间而扩大文档额度。
每次模型请求的输出预留固定为 2048，没有独立的输出 token 环境变量。

### 8.1 缓存与费用

缓存默认关闭。开启后只保存校验通过的结构化结果，没有 TTL 或自动清理服务。
键包含文档、分块、模型、endpoint、输出模式、提示词正文/版本、Schema 和输出预算。
缓存命中仍重新校验，不计作一次新的模型调用。

价格表默认没有模型报价，费用显示 `null`。
表项格式如下；0 只是格式占位，不是模型报价：

```json
{"models":{"your-provider-model":{"as_of":"2026-10-23","source":"https://provider.example/pricing","input_usd_per_million_tokens":0,"output_usd_per_million_tokens":0}}}
```

输入、输出分别按每百万 tokens 计费；缺日期、来源或有效数字时不计算费用。
provider 不返回完整 usage 时使用估算值，并明确标记；对应费用也只能视为估算。

## 9. 评测、质量检查与 Docker

```bash
make lint
make test
make check
.venv/bin/python -m eval.run_eval --output "$workflow_demo_dir/eval"
.venv/bin/python -m scripts.check_public
```

`make check` 只组合 lint 和 test；`make eval` 写入 `outputs/eval`。
`make format` 会执行 Ruff 自动修复与格式化，属于修改源码的维护命令。
`make campus-demo` 向 `outputs/campus/` 写入两份固定日期的审阅包。
评测器参数只有 `--output`、`--require-expectations` 与帮助选项。
它使用固定 `eval/cases.json` 的 40 条自建参考样例，不提供 `--dataset` 切换。
真实 provider 模式会关闭 Mock 故障注入，并可能调用外部服务。

```bash
.venv/bin/python -m eval.run_eval --output "$workflow_demo_dir/gated-eval" \
  --require-expectations
```

默认 Mock 集故意包含一条合法 Schema 的错分类，门禁命令预期返回非零。
成功报告数、指定字段精确匹配、类型正确、无支持字符串和预期结果分别计算分母。
Mock 分数和本机毫秒耗时不能解释为真实模型质量或推理性能。

```bash
docker build -t structured-llm-workflow:local .
docker run --rm -p 127.0.0.1:8102:8000 structured-llm-workflow:local
```

镜像内服务监听 `0.0.0.0:8000`，宿主机映射到 8102，容器默认 UID 10001。
容器健康检查访问内部 8000；无须把容器内部端口也改成 8102。
离线容器 CLI 可以写临时目录：

```bash
docker run --rm --network none structured-llm-workflow:local \
  python -m app.cli analyze examples/jd.txt --output /tmp/jd.json
```

`--rm` 退出后临时产物消失。保存到宿主机时需挂载目录并让运行 UID 有写权限：

```bash
mkdir -p outputs/container
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD/outputs/container:/results" structured-llm-workflow:local \
  python -m app.cli analyze examples/jd.txt --output /results/jd.json
```

## 10. 目录与模块职责

```text
structured-llm-workflow/
├── app/
│   ├── cli.py / api.py / campus.py       # 文件、HTTP、校园审阅入口
│   ├── domain/
│   │   ├── models.py                    # 严格结果、证据、冲突和用量模型
│   │   ├── provider.py                  # Provider 协议与请求/返回契约
│   │   └── errors.py                    # 安全错误与 partial 信息
│   ├── adapters/
│   │   ├── parser.py                   # 文本/PDF 解析与源位置
│   │   ├── mock.py                     # 离线标签/段落规则
│   │   ├── openai_compatible.py        # 兼容 HTTP 传输
│   │   └── fixtures/mock_rules.json    # 通用类型及字段标签
│   ├── fixtures/campus/                # 两份校园摘录与来源 manifest
│   ├── infra/
│   │   ├── config.py / prompts.py       # 配置校验与提示词摘要
│   │   └── cache.py / metrics.py        # 本地缓存、计数、价格与分位数
│   └── services/
│       ├── pipeline.py                 # 固定流程与部分失败信息
│       ├── model_service.py            # JSON、Schema、支持检查和修复
│       ├── chunking.py / merge.py       # 全文分块、去重与冲突合并
│       ├── grounding.py                # 连续原文匹配与 Evidence
│       ├── campus_review.py            # 招生业务检查及审阅单
│       └── exporter.py                 # 转义、JSON/Markdown 与原子写入
├── schema/model_registry.py            # 文档类型到提取 Schema 的唯一映射
├── prompts/                            # 分类、六类提取、分析、摘要、Reduce
├── config/prices.json                  # 可编辑的空价格表
├── examples/                           # JD、会议、论文、冲突、PDF、长文等
├── eval/cases.json / run_eval.py        # 固定参考数据与评测器
├── eval/results/mock/                  # 已提交的历史 Mock 快照
├── scripts/                            # 真实服务 smoke、公共内容扫描
├── tests/                              # 正常、故障、HTTP、来源与边界测试
├── docs/                               # 使用、架构、来源、验证与样例
├── pyproject.toml / uv.lock             # 项目声明与开发依赖锁
└── Dockerfile / requirements.lock       # 生产镜像与带哈希依赖
```

`outputs/`、`.cache/`、`.venv/` 和私人 `.env` 属于运行数据，不提交 Git。
API 不持久化请求；CLI 的报告、开启后的缓存以及调用方保存的 HTTP 响应需要自行管理。

## 11. 一次请求如何走完

1. Parser 检查大小与格式，生成 Document、段落和文本哈希。
2. Chunker 按换行优先拆分全文，超长单行按 Unicode 字符边界切分。
3. 每块分类；已知类型只有一种才采用，否则保持 unknown。
4. 按注册表选择 Schema，对每块提取并合并；列表去重，标量冲突置空。
5. 分析风险与冲突，分块摘要后按预算做层次 Reduce。
6. 每次模型输出都经过 JSON/Pydantic/原文支持检查；最终再次生成全局证据。
7. 成功报告汇总调用、用量、耗时与告警；CLI 导出，HTTP 返回 JSON。
8. 校园 CLI 额外匹配来源哈希、定位 DOCX 段落并执行审阅规则。

grounding 使用精确连续字符串匹配，不做语义蕴含判断。
摘要最多三个原文片段、总计不超过 192 个 UTF-8 字节估算单位。
Reduce 不能收敛时明确失败，不无限循环。
调用数、上下文、字节、字符与页数是独立限制，放宽一项不代表其他限制也被放宽。

## 12. 常见问题

| 现象 | 检查与处理 |
|---|---|
| `invalid_config` / 服务启动失败 | 核对 provider、URL、真实模型名和数值范围；环境变量可能覆盖 `.env` |
| `unsupported_type` | 使用 txt/md/pdf；不能仅把二进制文件改后缀 |
| `invalid_encoding` / `empty_or_binary` | 确认 UTF-8、非空正文、无 NUL |
| `ocr_not_supported` | PDF 无可提取文本，先在外部做 OCR |
| `encrypted_pdf` / `pdf_parse_error` | 使用未加密且结构有效的文本 PDF |
| `file_too_large` / `too_many_pages` | 拆分来源，或在实际资源允许时调整对应独立上限 |
| `context_budget_exceeded` | 减小源分块，或按服务能力提高上下文预算 |
| `call_budget_exceeded` | 缩小文档、减少修复，或明确提高调用上限 |
| `unsupported_claim` | 输出不含原文连续片段，不能靠放宽 JSON 格式解决 |
| `invalid_model_output` | 核对服务输出模式、模型能力与有限修复设置 |
| `provider_http_*` / `provider_protocol` | 检查 endpoint、模型名与兼容协议，不把错误当能力降级 |
| `source_mismatch` | 来源摘录或 manifest 已变化，重新核对并维护正确快照 |
| `output_conflict` | 为 JSON 和 Markdown 选择不同于来源的路径 |
| 8102 端口占用 | 关闭自己启动的旧进程，或显式换一个 uvicorn 端口 |

本项目的应用边界不包含恶意 PDF 的进程隔离、多用户认证或语义真实性保证。
进一步源码说明见 [代码导览](CODE_WALKTHROUGH.md)，资料权利与范围见 [校园资料说明](CAMPUS_DATA.md)。

## 13. 手册核对记录

本次按当前源码、CLI 帮助与独立临时目录核对：四类 CLI 文件报告、两份校园审阅包均生成成功；
40 条离线评测完成，39 条满足预期，严格门禁按设计退出 1。
本机 8102 的三个业务路由及四个文档路由均已请求；文本、PDF、校园文件上传、
额外字段、空白正文和不支持后缀的错误路径均已核对。临时 HTTP 服务已关闭。
现有 outputs 和历史评测快照未被这些核对命令覆盖；真实模型与 Docker 未在本次手册核对中运行。
