# 架构与边界

## 固定流程与类型

`Pipeline` 顺序调用 Parser → Classifier → Extractor → Analyzer → Summarizer → Validator。
CLI 再交给 Exporter；API 返回同一个 `AnalysisReport`，不默认写磁盘。
流程没有动态选工具、网页访问、shell 执行或自主规划。模型只提供数据。

| 层 | 文件 | 职责 |
|---|---|---|
| 入口 | `app/cli.py`, `app/api.py` | 参数/请求约束、结构化错误、导出或响应 |
| Domain | `app/domain/models.py`, `errors.py`, `provider.py` | 类型、报告、异常、Provider Protocol |
| Services | `pipeline.py`, `model_service.py`, `chunking.py`, `merge.py`, `grounding.py`, `exporter.py` | 固定编排与内容约束 |
| Adapters | `parser.py`, `mock.py`, `openai_compatible.py` | 文件/PDF、fixture、兼容 HTTP |
| Infra | `config.py`, `prompts.py`, `cache.py`, `metrics.py` | 环境配置、模板、缓存和可观测性 |
| Schema | `schema/model_registry.py` | DocumentType 对应模型与 JSON Schema 的唯一映射 |

Extraction 的每个字段都必须出现在 JSON 中；未知标量 `null`，未知列表 `[]`。
`extra="forbid"` 拒绝额外字段，strict 模式拒绝把数字强制转成字符串。
最终报告还检查 extracted 的具体模型与 type 匹配。

## Parser 与证据坐标

文本按 UTF-8 / UTF-8 BOM 解析，保留换行与 Unicode 字符顺序。
文本型 PDF 使用 pypdf，页面以 `\n\f\n` 拼接，每个非空行记录全局 start/end 与 1-based 页码。
Document 的 hash 对应解析后的文本，并非原始 PDF 字节。

限制顺序：输入 bytes → 类型/UTF-8 或 PDF → 页数/单页解压流大小 → 提取字符数。
PDF 单页解码流上限 8 MiB；这是解码后的检查，不能代替进程级内存/CPU 隔离。
加密文件拒绝；全无可提取文字时报告 `ocr_not_supported`，混合空页给出页号 warning。

Validator 对每个非空事实查找原文连续子串，生成 `field, quote, page, paragraph, start, end`。
end exclusive；相同 quote 取第一次出现位置。span 不能证明陈述的角色或真实性，
所以评测另有 gold 字段与 type accuracy。

## ModelService 与 Provider

每次 run 新建 ModelService，避免并发 API 请求的 records、预算和局部状态互相污染。
Provider 为轻量无会话对象。httpx 调用有超时，不跟随重定向，不自动重试 HTTP/超时错误。
真实服务需明确配置 base URL 和 model；密钥只存在 SecretStr 与 Authorization header。
Provider 错误体不进入用户响应，startup config error 也不打印带值的 Pydantic 错误。

ModelService：

1. 从外部版本化模板构造 system/user；源文编码为 JSON string，只放在 user 数据区。
2. 核对上下文预算，检查本次文档调用上限。
3. 调用 Provider；严格解析单个 JSON object，可接受完整 Markdown JSON fence。
4. 拒绝重复 JSON key、额外字段、不匹配类型和无源文支持的事实。
5. JSON / schema / span 失败时最多发配置次数的修复请求；默认 1、硬上限 2。
6. 每个真实尝试无论成功失败都写 CallRecord；仅已验证结果可进入缓存。

模式由 `WORKFLOW_RESPONSE_MODE` 显式声明：原生 strict JSON Schema、JSON object 或纯文本。
输出截断、拒绝、连接错误是独立 code，不伪装成有效报告。
Prompt injection 无工具执行面，但不能由此保证真实模型的语义行为完全不可被影响。

## 全文 Map/Reduce 与冲突

UTF-8 byte 代理预算按行优先切片，超长单行才按字符切开；拼接 chunks 等于完整原文。
每个 chunk 均参与四个模型阶段，不只检查开头。分类中仅一个明确类型时采用该类型；
出现多个明确类型时回到 unknown，并加 warning。

提取列表按出现顺序去重；标量多值不投票选择，置 null 并生成 Conflict。
Analyzer 另外报告同一 chunk 内显式冲突，保留各个候选的 source evidence。
这是有限冲突检测，不做任意语义推理；列表内容的逻辑矛盾需要人工审阅。

每个 chunk 产生抽取式摘要。短摘要拼接超预算时分组 Reduce，逐层缩短；
最后再 Reduce 成最多三个 span。每个摘要上限 192 UTF-8-byte 估算 tokens。
若 Reduce 没有缩短，明确失败 `reduce_not_converging`，不会截断并声称完整完成。
源 chunk、全上下文（含 schema / prompt / 输出预留）、总调用预算独立限制。

## 缓存与成本

缓存默认关闭。key 含整个文档 hash、chunk 内容 hash、endpoint/model/provider、
prompt digest 和实际正文、schema、输出 token 上限；API Key 不进入 key 或 value。
缓存 value 为已验证的输出，读取时再验证；损坏视作 miss。
写入使用 0700 目录、0600 临时文件与原子替换。缓存本身包含文档事实，是敏感本地数据。
无 TTL / 加密 / 访问审计，缓存开启者负责本机权限和清理。

真实 usage 优先；没有时用 UTF-8 bytes 估算，包含 prompt 与 schema。
`Usage.calls` 不含缓存，records 包含缓存事件；validation rate 和 P50/P95 针对实际尝试。
评测中的文档 latency 则包含整个 Pipeline，与单调用分位数不是同一个指标。
价格表必须有有效日期与来源 URL、非负有限单价，否则 cost=null。
估算 tokens 的费用仍是估算；无法从异常请求推断服务商实际账单。

## API 和失败状态

ASGI middleware 在 JSON/multipart 解析前限制真实读取 bytes，不信任 Content-Length。
上传再限制文件 bytes；纯文本再检查 UTF-8 bytes / 字符数。同步解析和模型调用在 threadpool 执行。
默认 API 不启用鉴权、限流或用户隔离，仅供本机演示。

WorkflowError 包含 `code / step / message / partial`。
partial 保留文档 hash、已完成步骤、已验证的提取结果（如果存在）与失败前 usage。
不会输出失败模型原始文本、secret 或 provider error body。
CLI 非零退出；API 文件超限 413、输入错误 422、模型超时 504、其他模型阶段错误 502。
`/health` 仅表示服务存活。请求失败不会导出标注 passed 的部分报告。

Exporter 单独负责 JSON/Markdown；用临时文件和原子替换写各个产物，Markdown 转义源文本，
JSON fence 随内容选择长度。两个文件分别原子写入，并非跨文件事务；磁盘写失败可能只留下一个产物。
CLI 检查输出扩展名和源路径，避免 JSON/Markdown 互相覆盖或覆盖输入。
