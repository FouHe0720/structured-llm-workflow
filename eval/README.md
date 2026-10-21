# 评测数据与指标定义

`cases.json` 有 40 条自建公开样例（五类各 8 条），每条包含显式固定 gold 字段，
覆盖中文、英文、混合语言、缺字段、50K 字符长文、冲突、恶意指令和 JSON/超时故障。
原文和 gold 一起编写，未调用 Mock 生成 gold，也未经过独立人工复核；不代表真实业务分布。
`examples/long_1000.txt` 与 `long_10000.txt` 另外由集成测试和 Demo 验证。
`fault` 仅用于 Mock 评测的**显式故障注入**；真实模型评测会禁用这些故障并移除对应 expected_error。

- **schema_validation_rate**：最终生成符合 schema 的报告数 / 全部文档数。
  包含预期拒绝的三条错误样例，因此这个比例无需等于 1。
- **call_validation_success_rate**：通过模型 JSON/schema/原文支持校验的实际调用数 / 实际调用总数。
  包含修复前失败和超时；缓存不纳入。
- **required_field_accuracy**：与逐条 gold 完全相同的指定字段数 / 全部 gold 字段数。
  字段均计入，包含 null/[]；失败文档所有字段计错，错误分类缺失的字段计错；列表按顺序严格匹配。
- **type_accuracy**：分类与 gold 一致的报告数 / 全部文档数（失败文档计错）。
- **unsupported_claim_rate**：最终报告的 extracted、summary、risks/highlights、conflicts 中
  无连续原文 span 支持的非空字符串数 / 这些字段的非空字符串总数。
  由独立 evaluator 遍历输出再检查原文；这是 span 支持指标，**不能证明语义正确或事实真实**。
  生产 Validator 已拒绝无支持内容，因此通常为 0；另记 rejected_unsupported_attempts 观测被拒绝的尝试。
- **P50/P95 latency**：所有文档从解析至成功/失败的 wall time，nearest-rank，包含故障样例。
- **expectation_met**：正确报告（类型、全部 gold 字段、冲突一致），或匹配预期拒绝错误。
  `pa07` 故意注入 schema 合法但类型错误的分类，用来证明 schema 通过不等于任务正确；评测应检测它。

结果 JSON 包含逐条行与总表，CSV 便于分析，Markdown 用于展示。数值仅对应本次本机运行，
Mock 延迟不是实际 LLM 推理性能。程序错误不会伪装成模型失败；评测默认不设准确率门槛。
使用 `--require-expectations` 可启用任务正确性门禁（故意错分的 Mock 套件会返回非零）。
