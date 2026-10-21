# 阅读顺序与面试追问

## 先读这五个源文件

1. `app/domain/models.py`：理解五类 extraction、Report、Evidence、Conflict 与 Usage 的契约。
2. `app/adapters/parser.py`：理解 bytes / chars / pages 约束及 PDF 全局 Unicode offsets。
3. `app/services/model_service.py`：读清缓存 → Provider → 严格 JSON → Pydantic → span → 有限修复与 finally 记录。
4. `app/services/pipeline.py`：理解固定步骤、全文 Map/Reduce、冲突合并与 partial failure。
5. `eval/run_eval.py`：理解 gold 对照、失败分母、故障注入和合法 schema 的错分类如何被检出。

然后对照 `schema/model_registry.py`、`app/adapters/openai_compatible.py` 和 `prompts/`，再跑 DEMO。

## 1. 为什么是 Workflow，而不是 Agent？

步骤、顺序、调用预算、可用输入都由代码决定。模型只能返回受限数据，不能决定调用 shell、
浏览器或新工具。本需求是可重复文档分析，固定流程更易测量与诊断；没有加入 Agent 框架的必要。
若未来需要自主规划跨来源调查，那是新的需求和新的权限边界。

## 2. JSON mode、Structured Output 和 Pydantic 分别解决什么？

JSON mode 帮助输出可解析 JSON；JSON Schema 模式对结构施加服务端约束；本地 Pydantic
仍检查字段、枚举、类型和 extra keys，并为不支持原生 schema 的服务提供统一边界。
代码还拒绝重复 JSON key，避免常规 json.loads 覆盖前值。三者都不能证明事实正确。

## 3. 为什么保留 null / []，而不让模型“补全”？

缺失就是信息状态。JD 年限、论文作者、会议时间如果源文未提供，补全会污染下游数据。
所有 schema 字段都是必填 key，但值可以 nullable / empty list；API 消费方能区分未知与缺少 key。
测试与 gold 也直接检查空值，而不是只检查字段存在。

## 4. 如何处理 Hallucination 与证据？

每个输出事实必须为连续原文 quote，最终统一生成段落/页码/span；无支持的内容有限修复后仍失败就拒绝。
这种抽取式约束牺牲改写自由度，便于机械审计。它不能识别“引用的是错误人物的年限”等语义错误，
也不能判断源文本真实。因此 evaluator 另外比较手工定义的 gold 字段，不把 span 支持率当真实性。

## 5. Prompt 版本怎样进入可复现性与缓存？

prompt 文件位于代码外的 `prompts/*.md`，有 system/user、JSON 示例和语义版本。
PromptStore 对全部模板内容生成 digest，写进 model_info；缓存还包含实际消息、schema、
模型/endpoint、文档 hash 和输出预算。改 prompt 或模型不会误读旧结果。
当前 digest 覆盖全部模板，因此改一个模板也会让所有阶段缓存失效，是简单但保守的取舍。

## 6. 长文为什么要 Map/Reduce？会丢信息吗？

上下文有上限，直接截断会丢尾部。本项目把所有字符分配给 chunks，四阶段覆盖每个 chunk，
再层次 Reduce 摘要；列表去重、标量冲突保留候选并置空。摘要本身必然选择信息；
跨 chunk 关系、被切开的长字段和语义冲突仍可能丢失，代码有 warning 或明确失败。
真实运行的 50K 字符样例用尾部 TailEvidence 验证没有只处理开头。

## 7. 字符、tokens、价格之间有什么区别？

字符是 Unicode 计数；模型 tokens 依赖 tokenizer。本项目离线使用 UTF-8 bytes 作保守代理，
不把估算记成 Provider usage。上下文预算还包含 prompt/schema 与输出预留。
价格按输入/输出 tokens 单独计算，只有带日期与来源 URL 的表项才启用；默认 cost=null。
模型调用上限和 repair 上限限制放大，但并非服务商账单级预算或硬美元限额。

## 8. 超时和坏 JSON 怎样恢复？为什么不无限重试？

坏 JSON、schema 错误和无支持断言最多修复配置次数，默认一次；每个失败尝试也计入 calls、延迟和 usage。
超时、401、429、拒绝、输出 token 截断直接返回对应 code。无限重试会放大费用和故障，
也无法修复不兼容协议。本项目显式选择 response mode，而不是把所有 400 自动当作功能降级。
partial 保留已完成阶段、已经通过校验的 extraction 与失败记录。

## 9. 如何防止 Prompt injection？能宣称完全解决吗？

文档只出现在 JSON 编码的 user 数据中，system 声明它是不可信内容；没有工具执行接口，
密钥不放进 prompt，输出再做 schema/span 校验。fixture 负例验证了恶意指令不会触发执行或凭据泄露。
这些边界不能证明外部 LLM 的语义判断完全不受干扰；真实模型仍需要专门红队评测。
本项目没有运行外部模型，不做这种保证。

## 10. 怎么证明评测不是只看“格式通过”？

40 条显式 gold 不从 Mock 输出生成。evaluator 对比每个指定字段、类型与冲突，并重新检查 span 支持。
`pa07` 故意注入 meeting_minutes 分类到 paper_abstract 文档，结果 schema 合法，但 gold 不匹配。
因此套件 39/40 满足预期，而不是伪造全绿。三条预期失败仍计入 schema/字段指标分母。
Mock 延迟不是推理性能；数据未获独立人工复核，也不代表真实分布。

## 三个可继续思考的问题

- 如果一句原文同时包含两个人的不同任职年限，如何在 span 支持之外评测字段归属？
- 怎样增加重叠 chunk 或结构化中间事实，又保证调用预算与缓存隔离仍可审计？
- 上线给多用户后，应如何设计 PDF 解析隔离、缓存保留策略、鉴权和费用配额？
