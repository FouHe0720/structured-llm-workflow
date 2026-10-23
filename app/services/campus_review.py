"""Admission intake checks: evidence validation does not authorize publication."""

import re
from datetime import date

from app.domain.errors import WorkflowError
from app.domain.models import AnalysisReport, CampusAdmissionInfo
from app.services.exporter import code_block, literal


def admission_review(report: AnalysisReport, source: dict, as_of: date) -> dict:
    if not isinstance(report.extracted, CampusAdmissionInfo):
        raise WorkflowError("wrong_document_type", "Expected a campus admission notice")
    if source["excerpt_sha256"] != report.metadata.sha256:
        raise WorkflowError("source_mismatch", "Excerpt does not match the source manifest")
    fields = report.extracted.model_dump()
    issues: list[dict] = []

    def issue(code: str, field: str, message: str) -> None:
        issues.append({"code": code, "field": field, "message": message})

    for field in ("title", "audience", "registration_window", "quota_rules"):
        if not fields[field]:
            issue("missing_field", field, "摘录未提供完整信息，需查阅原通知。")
    window = fields["registration_window"] or ""
    if re.search(r"中午\s*(?:1[3-9]|2[0-3])\s*(?:点|[：:])", window):
        issue(
            "ambiguous_time", "registration_window", "原文将“中午”与下午时刻并用，保留原文待核对。"
        )
    if window and not re.search(r"20\d{2}年", window):
        issue("year_not_explicit", "registration_window", "报名时间未写年份，不自动补全日期。")
    if source["year"] < as_of.year:
        issue(
            "historical_source", "source.year", "这是一份历史招生材料，不能直接作为本年度安排发布。"
        )
    quotas = {
        match.group(1)
        for rule in fields["quota_rules"]
        for match in re.finditer(r"(?:录取|计划人数为)\s*(\d+)", rule)
    }
    if len(quotas) > 1:
        issue("conflicting_quota", "quota_rules", "招生名额出现不同数字，保留各处原文待核对。")
    for conflict in report.conflicts:
        issue("conflicting_values", conflict.field, "存在多个原文候选，需逐项核对。")
    source_evidence = []
    for evidence in report.evidence:
        paragraph = next(
            (item["index"] for item in source["paragraphs"] if evidence.quote in item["text"]),
            None,
        )
        source_evidence.append({**evidence.model_dump(), "source_paragraph": paragraph})
    return {
        "status": "needs_human_review",
        "as_of": as_of.isoformat(),
        "source": {key: value for key, value in source.items() if key != "paragraphs"},
        "issues": issues,
        "evidence": source_evidence,
        "report": report.model_dump(mode="json"),
    }


def _cell(value: str) -> str:
    return literal(value).replace("\r\n", "\n").replace("\n", "<br>")


def review_markdown(packet: dict) -> str:
    fields, source = packet["report"]["extracted"], packet["source"]
    labels = {
        "title": "标题",
        "audience": "报名对象",
        "registration_window": "报名时间",
        "quota_rules": "招生名额",
        "selection_rules": "选拔规则",
        "restrictions": "报名限制",
        "summary": "摘要",
        "source": "资料来源",
    }
    lines = [
        "# 招生材料审阅单",
        "",
        literal(fields["title"] or "未提取到标题"),
        "",
        f"**待人工核对** · 审阅日期 {literal(packet['as_of'])} · "
        f"{source['year']} 年资料 · {literal(source['campus'])}",
        "",
        f"> {len(packet['issues'])} 项待核对。结构与原文校验通过不代表材料可以直接发布。",
        "",
        "## 需要核对",
        "",
    ]
    if packet["issues"]:
        lines.extend(["| 检查项 | 涉及信息 | 核对说明 |", "|---|---|---|"])
        for issue in packet["issues"]:
            field = labels.get(issue["field"].split(".")[0], issue["field"])
            lines.append(f"| `{issue['code']}` | {_cell(field)} | {_cell(issue['message'])} |")
    else:
        lines.append("未命中现有规则，仍须核对材料完整性与适用范围。")
    lines.extend(["", "## 招生信息", "", "| 项目 | 原文 |", "|---|---|"])
    for key in ("audience", "registration_window"):
        lines.append(f"| {labels[key]} | {_cell(fields[key] or '未提供')} |")
    lines.extend(["", "## 录取与考核", ""])
    rules = dict.fromkeys(
        fields["quota_rules"] + fields["selection_rules"] + fields["restrictions"]
    )
    lines.extend(f"- {literal(item)}" for item in rules)
    if not rules:
        lines.append("摘录未提供录取与考核规则。")
    grouped: dict[tuple, list[str]] = {}
    for item in packet["evidence"]:
        key = (item["source_paragraph"], item["quote"])
        field = item["field"].removeprefix("extracted.").split(".")[0]
        label = labels.get(field, field)
        if label not in grouped.setdefault(key, []):
            grouped[key].append(label)
    lines.extend(
        [
            "",
            "## 证据与来源",
            "",
            f"来源：{literal(source['title'])}。原文定位以 DOCX 段落编号为准。",
            "",
            f"<details><summary>查看原文证据（{len(grouped)} 条）</summary>",
            "",
            "| 信息 | 原文位置 | 引文 |",
            "|---|---|---|",
        ]
    )
    for (paragraph, quote), names in grouped.items():
        location = f"第 {paragraph} 段" if paragraph is not None else "摘录元数据"
        lines.append(f"| {'、'.join(names)} | {location} | {_cell(quote)} |")
    lines.extend(
        [
            "",
            "</details>",
            "",
            "<details><summary>查看来源记录与文件指纹</summary>",
            "",
            code_block(source),
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)
