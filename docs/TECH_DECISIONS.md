# 技术决策

1. **固定 Workflow**：不引入 LangGraph、Agent 或多 Agent；顺序边界由 Pydantic 类型和异常状态表达。
2. **Python 3.10+、项目 venv**：系统 Python 缺少 ensurepip；改用已安装的 `uv venv --allow-existing .venv`，实际选择 Python 3.12.15，无系统安装。
3. **httpx + Chat Completions**：兼容自建/第三方服务，JSON Schema 优先；不支持时显式选择 `json_object` 或 `text`，不自动把认证/限流错误当成能力降级。
4. **可验证的抽取式输出**：每个非空值要求原文连续 span；牺牲自由改写，便于机械验证。出现原文不意味着语义正确；不提供事实真实性担保。
5. **UTF-8 bytes 保守估算**：不下载模型 tokenizer，字符数与 tokens 分开记录。配置源 chunk、上下文（含 prompt/schema/输出预留）与总调用上限；超预算明确失败，不截断源文。
6. **Map/Reduce**：分类/提取/分析/摘要均覆盖全部 chunk；列表去重，标量冲突置空并保留全部候选；层次 Reduce 强制收缩，失败返回诊断。摘要最多三个原文 span、合计 192 估算 tokens。
7. **pypdf**：文本型 PDF 保留页码；加密/扫描 PDF 明确拒绝，空白混合页给出 warning。解析不是恶意 PDF 沙箱，公开部署需进程资源隔离。
8. **缓存默认关闭**：只缓存已验证输出，本机 0700 目录/0600 文件；key 包含 provider/endpoint/model、内容 hash、prompt 内容与版本、schema、输出预算。缓存无 TTL，需要时删除项目 `.cache/workflow`；多进程写入用原子替换。
9. **本机 API**：默认监听 127.0.0.1；没有认证/限流，公网部署前需网关。输入大小在解析 JSON/multipart 之前限制，路由再检查文件与文本大小。
10. **价格不猜测**：`config/prices.json` 默认空；需逐模型填写日期、来源和输入/输出单价。错误请求可能被服务商计费，本项目只能记录已知/估算 usage。

协议参考（核对日期 2026-10-21）：[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat)。JSON mode 只约束 JSON，仍需本地 schema 验证；strict schema 也不能保证事实正确。
