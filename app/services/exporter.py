"""Atomic local export. Untrusted content is escaped before Markdown rendering."""

import json
import os
import re
import tempfile
from pathlib import Path

from app.domain.errors import WorkflowError
from app.domain.models import AnalysisReport


def literal(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|~\-])", r"\\\1", value)


def code_block(value: object) -> str:
    content = json.dumps(value, ensure_ascii=False, indent=2)
    fence = "`" * max(3, max((len(m.group()) for m in re.finditer(r"`+", content)), default=0) + 1)
    return f"{fence}json\n{content}\n{fence}"


def markdown(report: AnalysisReport) -> str:
    lines = [
        "# Document Intelligence Report",
        "",
        f"Type: `{report.type.value}` | Validation: `{report.validation_status}`",
        "",
        "## Summary",
        "",
        literal(report.summary),
        "",
        "## Extracted",
        "",
        code_block(report.extracted.model_dump()),
        "",
        "## Risks and highlights",
        "",
        code_block(report.risks_or_highlights.model_dump()),
        "",
        "## Conflicts",
        "",
        code_block([c.model_dump() for c in report.conflicts]),
        "",
        "## Evidence (Unicode offsets, end exclusive)",
        "",
    ]
    for item in report.evidence:
        lines.append(
            f"- `{item.field}`: {literal(item.quote)} "
            f"(page={item.page}, paragraph={item.paragraph}, span={item.start}:{item.end})"
        )
    lines += [
        "",
        "## Model and usage",
        "",
        code_block(
            {
                "model_info": report.model_info,
                "usage": report.usage.model_dump(),
                "timings": report.timings,
            }
        ),
        "",
        "## Warnings",
        "",
        *[f"- {literal(w)}" for w in report.warnings],
    ]
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, content: str) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def export(report: AnalysisReport, output: Path) -> None:
    if output.suffix != ".json":
        raise WorkflowError("invalid_output", "Output must end with .json", step="exporter")
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(output, report.model_dump_json(indent=2))
    atomic_write(output.with_suffix(".md"), markdown(report))
