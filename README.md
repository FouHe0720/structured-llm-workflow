# 校园招生材料审阅 · Structured LLM Workflow

[![CI](https://github.com/FouHe0720/structured-llm-workflow/actions/workflows/ci.yml/badge.svg)](https://github.com/FouHe0720/structured-llm-workflow/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

把招生简章整理成可核对的报名信息，保留原文、来源段落和待确认项。
示例来自山东大学（威海）2024 年招生资料；通用工作流仍支持招聘 JD、论文摘要、会议纪要、技术报告与未知文本。

默认离线运行，不需要模型服务或 API Key。Python 3.10+ · Pydantic · FastAPI · httpx · pypdf。

完整操作说明见 [使用手册](docs/USER_GUIDE.md)：安装启动、全部命令/API、配置与实现结构。

## 先看一个具体问题

智能导航特色班的原文写着：**“报名时间：2024年9月1日起至9月9日中午14点结束。”**
程序照原文提取，把“中午14点”列入待核对项，不擅自改成某个标准时间。
计算法学简章中的招生人数、面试入围比例与成绩权重分别保留，避免把“1∶1.2”当成招生名额。

```text
历史招生简章 → 分类 / 提取 → Schema + 原文 span 校验
                              ↓
                      缺项、日期歧义、名额冲突检查
                              ↓
                    JSON 审阅包 + Markdown 审阅单
```

审阅包始终是 `needs_human_review`。格式和原文校验通过，不代表材料适合直接发布。

## 运行

```bash
make install
make campus-demo
make check
```

查看 `outputs/campus/navigation.md` 和 `outputs/campus/law.md`，或运行单份材料：

```bash
.venv/bin/python -m app.campus \
  --source-id navigation-admission-2024 \
  --as-of 2026-10-23 \
  --output outputs/review.json
```

`--as-of` 是显式的审阅日期。演示固定使用该日期，以便重复得到相同的历史年份检查结果。
每份输出包含报名对象、报名时间、名额与考核原文、问题清单，以及回到原 DOCX 的段落编号。
[样例审阅单](docs/samples/navigation-review.md)可直接阅读，无需安装。

## 业务边界如何落在代码里

| 处理环节 | 实现 |
|---|---|
| 信息缺失 | 标量保持 `null`、列表保持 `[]`；关键缺项进入审阅清单 |
| 原文定位 | 每个事实记录 Unicode `start:end`、解析段落；校园包另关联原 DOCX 段落 |
| 矛盾与歧义 | 标量冲突置空并保留候选；名额数字冲突、日期缺年份、时刻表述歧义分别标记 |
| 长文 | 全文分块 Map/Reduce，不截掉尾部；跨块关系可能需要人工核对 |
| 模型失败 | 严格 JSON/Pydantic 校验，最多有限次数修复，记录失败调用与预算 |
| 可追溯来源 | 保存原文件与摘录的 SHA-256、资料年份、年级和校区 |

校园离线提取是针对这两份摘录的段落规则，不具备通用语义理解能力。
接入兼容模型后，仍经过同一套 Schema 和原文证据校验；有原文支持也不能证明内容本身正确。

## 通用入口

```bash
.venv/bin/python -m app.cli analyze examples/jd.txt --output outputs/jd.json
.venv/bin/python -m app.cli analyze examples/sample.pdf --output outputs/pdf.json
make serve
```

API 提供 `POST /v1/analyze`、`POST /v1/analyze/file`，交互文档在 `http://127.0.0.1:8000/docs`。
默认仅监听本机，无认证；上传上限 2 MiB，解析后最多 200,000 字符 / 50 页，扫描 PDF 不做 OCR。
每次生成 JSON 与 Markdown，含模型调用、耗时、token 来源和告警。缓存默认关闭；价格表为空时费用为 `null`。

真实模型使用 `.env.example` 中的 `WORKFLOW_PROVIDER`、`WORKFLOW_BASE_URL`、`WORKFLOW_MODEL` 等设置，
通过兼容的 `/chat/completions` 接口调用。配置与限制见 [演示说明](docs/DEMO.md)和[技术决策](docs/TECH_DECISIONS.md)。
真实外部模型未在本次验证中调用。

## 资料与验证

校园材料由本地 RAG 知识库选取了两份历史招生简章，共 20 个原文段落。
[来源清单](app/fixtures/campus/manifest.json)记录文件相对路径、原始 DOCX 哈希、摘录哈希与段落编号；
没有收录个人电话、邮箱或名单。摘录不代表当前招生安排，原文权利归原作者，代码 MIT 许可不覆盖学校材料。

2026-10-23 本地验证：**68 项测试通过**，Ruff 检查通过，两个校园审阅命令通过。
测试覆盖原文定位、来源不匹配、日期歧义、历史年份、名额冲突，以及原有上传、预算、失败与 PDF 边界。
有一条 Starlette/httpx 上游弃用提示。Docker 与托管 CI 的历史记录见[验证记录](docs/VERIFICATION.md)，本次未重新构建镜像。

原有 40 条自建 Mock 评测继续保留在 [eval](eval/README.md)，不与这两份校园材料混作真实模型准确率。

- [架构](docs/ARCHITECTURE.md) · [演示](docs/DEMO.md) · [校园资料说明](docs/CAMPUS_DATA.md)
- [代码导览](docs/CODE_WALKTHROUGH.md)
- [MIT 代码许可证](LICENSE)
