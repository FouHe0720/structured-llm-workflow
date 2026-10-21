# 基于已完成实现的简历描述

- 使用 Python、Pydantic、FastAPI、httpx 与 pypdf 实现固定文档分析 Workflow，支持 JD、论文摘要、会议纪要和技术报告的结构化提取、抽取式摘要，以及段落/页码/span 级证据追溯；提供离线 Mock、CLI 和 HTTP API。
- 实现外部版本化 prompts、OpenAI-compatible JSON Schema/JSON mode 接口、有限输出修复、全文 Map/Reduce、标量冲突保留、调用预算与真实/估算用量区分；完成 1K/10K/50K 字符样例验证。
- 建立 40 条自建固定 gold 评测、JSON/CSV/Markdown 导出与 60 个自动化测试，覆盖坏 JSON、错分类、超时、恶意输入、PDF 和上传边界；交付 CI 与已实跑的非 root Docker 镜像。

使用时应能亲自演示 `make demo` 和解释 `pa07` 故意错分类。不要把 Mock 指标写成真实模型准确率、
把本机延迟写成生产推理性能，或编造效率提升百分比。gold 未获独立人工复核，真实外部模型未实测。
