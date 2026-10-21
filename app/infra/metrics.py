"""Honest usage accounting: estimated tokens never silently become provider usage."""

import json
import math
from datetime import date
from pathlib import Path

from app.domain.models import CallRecord, Usage


def conservative_tokens(text: str) -> int:
    # UTF-8 bytes are a conservative upper-bound proxy for common byte BPE tokenizers.
    # This is not exact tokenization, and arbitrary provider tokenizers may differ.
    return len(text.encode("utf-8"))


def percentile(values: list[float], quantile: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)] if values else 0.0


class PriceTable:
    def __init__(self, path: Path) -> None:
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        if not isinstance(self.data, dict) or not isinstance(self.data.get("models", {}), dict):
            self.data = {}

    def cost(self, model: str, record: CallRecord) -> float | None:
        row = self.data.get("models", {}).get(model)
        if not isinstance(row, dict) or not row.get("as_of") or not row.get("source"):
            return None
        try:
            date.fromisoformat(row["as_of"])
            if not row["source"].startswith(("https://", "http://")):
                return None
            a = float(row["input_usd_per_million_tokens"])
            b = float(row["output_usd_per_million_tokens"])
            if not (math.isfinite(a) and math.isfinite(b) and a >= 0 and b >= 0):
                return None
            return (record.input_tokens * a + record.output_tokens * b) / 1_000_000
        except (ValueError, TypeError, KeyError, AttributeError):
            return None


def aggregate(records: list[CallRecord]) -> Usage:
    calls = [r for r in records if not r.cache_hit]
    costs = [r.cost_usd for r in calls]
    return Usage(
        calls=len(calls),
        cache_hits=len(records) - len(calls),
        input_tokens=sum(r.input_tokens for r in calls),
        output_tokens=sum(r.output_tokens for r in calls),
        token_source="+".join(sorted({r.token_source for r in calls})) or "cache",
        cost_usd=sum(costs) if costs and all(c is not None for c in costs) else None,
        validation_success_rate=sum(r.success for r in calls) / len(calls) if calls else 1.0,
        p50_ms=percentile([r.elapsed_ms for r in calls], 0.5),
        p95_ms=percentile([r.elapsed_ms for r in calls], 0.95),
        records=records,
    )
