"""Safe local JSON and Markdown export."""

import json
from pathlib import Path

from app.domain.models import AnalysisReport


def markdown(report: AnalysisReport) -> str:
    lines = [
        "# Document Intelligence Report",
        "",
        f"Type: `{report.type.value}` | Validation: `{report.validation_status}`",
        "",
        "## Summary",
        "",
        report.summary,
        "",
        "## Extracted",
        "",
        "```json",
        json.dumps(report.extracted.model_dump(), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Evidence (Unicode offsets, end exclusive)",
        "",
    ]
    for item in report.evidence:
        lines.append(
            f"- `{item.field}`: {item.quote!r} "
            f"(page={item.page}, paragraph={item.paragraph}, span={item.start}:{item.end})"
        )
    lines += ["", "## Warnings", "", *[f"- {w}" for w in report.warnings]]
    return "\n".join(lines) + "\n"


def export(report: AnalysisReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
