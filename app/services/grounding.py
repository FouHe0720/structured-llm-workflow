"""Deterministic support checks: every output claim must be a verbatim source span."""

from collections.abc import Iterator
from typing import Any

from app.domain.errors import WorkflowError
from app.domain.models import Document, Evidence


def claims(value: Any, prefix: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from claims(item, f"{prefix}.{key}" if prefix else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from claims(item, f"{prefix}.{index}")
    elif isinstance(value, str) and value:
        yield prefix, value


def evidence_for(document: Document, values: Any, prefix: str = "") -> list[Evidence]:
    result = []
    for field, quote in claims(values, prefix):
        start = document.text.find(quote)
        if start < 0:
            raise WorkflowError(
                "unsupported_claim", f"Output field lacks a source span: {field}", step="validator"
            )
        segment = next(
            (s for s in document.segments if s.start <= start < s.end), document.segments[0]
        )
        result.append(
            Evidence(
                field=field,
                quote=quote,
                page=segment.page,
                paragraph=segment.paragraph,
                start=start,
                end=start + len(quote),
            )
        )
    return result
