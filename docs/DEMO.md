# 校园招生审阅演示

```bash
make install
make campus-demo
```

查看 `outputs/campus/navigation.md`：报名对象保留不得转专业的限制，名额原文包含 30 名，
`ambiguous_time` 指向“9月9日中午14点”；`historical_source` 提醒这是 2024 年材料。
`outputs/campus/law.md` 保留招生人数与面试入围比例，`year_not_explicit` 提醒报名时间本身没有年份。
两份报告都进入待人工审阅状态。审阅单先列需要核对的问题，再列招生信息和选拔规则；
去重后的原文证据与文件指纹可展开查看。完整字段与原文位置保存在相邻 JSON 中。

下方保留通用文档、HTTP、长文、Docker 和真实模型配置的演示步骤。

# 可复制演示

所有命令在本仓库根目录的 WSL / Linux 终端执行。默认没有 `.env` 或保持 `WORKFLOW_PROVIDER=mock`。
首次安装需要下载 Python 依赖；后续不需要网络、GPU 或 LLM Key。

## 1. 安装并验证

```bash
make install
make check
```

首版本机实跑 60 个 pytest 通过；1 条 Starlette/httpx 弃用提示不影响结果。

## 2. JD → JSON / Markdown

```bash
.venv/bin/python -m app.cli analyze examples/jd.txt --output outputs/jd.json
cat outputs/jd.json
cat outputs/jd.md
```

观察：`type=job_description`；experience=null，没有编造年限。
每条 evidence 的 quote 可以在输入原文中定位。

## 3. 多类型与恶意输入

```bash
.venv/bin/python -m app.cli analyze examples/paper.md --output outputs/paper.json
.venv/bin/python -m app.cli analyze examples/meeting.txt --output outputs/meeting.json
.venv/bin/python -m app.cli analyze examples/report.txt --output outputs/report.json
.venv/bin/python -m app.cli analyze examples/injection.txt --output outputs/injection.json
.venv/bin/python -m app.cli analyze examples/conflict.txt --output outputs/conflict.json
```

论文作者缺失保持 []；会议纪要保留中文；恶意文档没有工具调用或密钥访问行为。
conflict 样例的 experience=null，conflicts.values 同时保留 `2 years` 与 `5 years`。
Mock 不理解任意自然语言，只按 fixture 的标题/标签规则返回。

## 4. PDF 页码与长文

```bash
.venv/bin/python -m examples.generate
.venv/bin/python -m app.cli analyze examples/sample.pdf --output outputs/pdf.json
.venv/bin/python -m app.cli analyze examples/long_1000.txt --output outputs/long_1000.json
.venv/bin/python -m app.cli analyze examples/long_10000.txt --output outputs/long_10000.json
.venv/bin/python -m app.cli analyze examples/long_50000.txt --output outputs/long_50000.json
```

生成器只用 CPU 和 pypdf，自建两页文本型 PDF；第二页限制项的 evidence.page=2。
50K 文本恰好 50,000 个字符、默认 43 chunks / 173 次 Mock 调用；末尾 Skills=TailEvidence 保留。
摘要自然会缩短内容；源文处理不截断。扫描 PDF 会明确失败，不伪装成已经 OCR。

## 5. 启动 HTTP 服务

终端 A：

```bash
make serve
```

终端 B：

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"Job Description\nPosition: Reviewer\nSkills: Python"}'
curl -s http://127.0.0.1:8000/v1/analyze/file -F 'file=@examples/sample.pdf'
curl -s http://127.0.0.1:8000/v1/analyze \
  -H 'Content-Type: application/json' -d '{"text":""}'
```

前三条成功；最后一条返回结构化 `invalid_request` 与 HTTP 422。
结束服务用终端 A 的 Ctrl-C。仅监听 127.0.0.1。

## 6. 评测与错误恢复

```bash
make eval
cat outputs/eval/SUMMARY.md
.venv/bin/python -m pytest -q tests/test_core.py tests/test_boundaries.py
```

输出 JSON/CSV/Markdown 三种结果；其中包含有限 JSON 修复、Pydantic 类型修复、
超时、unsupported_claim 拒绝和故意错分类。gold 来源与各分母见 `eval/README.md`。

以下命令**预期非零退出**：

```bash
.venv/bin/python -m eval.run_eval --require-expectations --output outputs/eval-gate
```

原因是 `pa07` 故意给出 schema 合法但错误的类型；不要删掉失败行来提高分数。

## 7. Docker（本机已实测）

```bash
docker build -t structured-llm-workflow:local .
docker run --rm structured-llm-workflow:local \
  python -m app.cli analyze examples/jd.txt --output /tmp/report.json
docker run --rm -p 127.0.0.1:8000:8000 structured-llm-workflow:local
```

容器 CLI 的输出是临时文件；最后一条保持运行，另开终端用第 5 步 curl 验证。
默认不挂载宿主私有目录，不向公网绑定；容器进程 UID 10001。

## 8. 自选真实模型验证

填写 `.env`（只在本机）：provider=openai、base URL、model、按需 Key。
确认自己的服务与费用后执行：

```bash
.venv/bin/python -m scripts.smoke_real
.venv/bin/python -m eval.run_eval --output outputs/real-eval
```

本次交付没有运行这两条真实模型命令，不提供未经测量的模型准确率。
