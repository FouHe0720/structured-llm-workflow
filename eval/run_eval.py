"""Reproducible gold evaluation. Run: python -m eval.run_eval --output outputs/eval."""

import argparse
import csv
import hashlib
import json
import platform
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.adapters.mock import MockLLM
from app.domain.errors import WorkflowError
from app.domain.provider import Completion, ModelRequest
from app.infra.config import Settings
from app.infra.metrics import percentile
from app.infra.prompts import PromptStore
from app.services.grounding import claims
from app.services.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]


class FaultFixture(MockLLM):
    def __init__(self, fault: dict) -> None:
        super().__init__()
        self.fault = fault
        self.responses = list(fault.get("responses", []))
        self.error_sent = False

    def complete(self, request: ModelRequest) -> Completion:
        if request.step == self.fault.get("step"):
            if self.fault.get("error") and not self.error_sent:
                self.error_sent = True
                raise WorkflowError(self.fault["error"], "Explicit evaluation fault injection")
            if self.responses:
                return Completion(self.responses.pop(0))
        return super().complete(request)


def evaluate(cases: list[dict], settings: Settings) -> dict:
    rows = []
    total_fields = correct_fields = claim_count = unsupported = 0
    call_count = valid_calls = rejected_claims = 0
    for case in cases:
        text = (ROOT / case["file"]).read_text(encoding="utf-8") if "file" in case else case["text"]
        fault = case.get("fault", {}) if settings.provider == "mock" else {}
        expected_error = case.get("expected_error") if settings.provider == "mock" else None
        pipeline = Pipeline(
            provider=FaultFixture(fault) if settings.provider == "mock" else None, settings=settings
        )
        start = time.perf_counter()
        row = {
            "id": case["id"],
            "expected_type": case["type"],
            "actual_type": None,
            "schema_valid": False,
            "correct_fields": 0,
            "total_fields": len(case["expected"]),
            "error": None,
            "expected_error": expected_error,
            "expectation_met": False,
        }
        total_fields += len(case["expected"])
        records = []
        try:
            report = pipeline.run(pipeline.parser.parse_text(text, case["id"] + ".txt"))
            output = report.extracted.model_dump()
            matched = sum(
                key in output and output[key] == value for key, value in case["expected"].items()
            )
            correct_fields += matched
            row.update(actual_type=report.type.value, schema_valid=True, correct_fields=matched)
            actual_conflicts = {c.field: c.values for c in report.conflicts}
            row["expectation_met"] = (
                not expected_error
                and report.type.value == case["type"]
                and matched == len(case["expected"])
                and actual_conflicts == case.get("conflicts", {})
            )
            payload = {
                "extracted": output,
                "summary": report.summary.splitlines(),
                "analysis": report.risks_or_highlights.model_dump(),
                "conflicts": [c.values for c in report.conflicts],
            }
            for _, claim in claims(payload):
                claim_count += 1
                unsupported += claim not in text
            records = [r.model_dump() for r in report.usage.records]
        except WorkflowError as exc:
            row["error"] = exc.code
            row["expectation_met"] = expected_error == exc.code
            records = exc.partial.get("usage", {}).get("records", [])
        row["latency_ms"] = (time.perf_counter() - start) * 1000
        for record in records:
            if not record["cache_hit"]:
                call_count += 1
                valid_calls += record["success"]
                rejected_claims += record["error_code"] == "unsupported_claim"
        rows.append(row)
    count = len(rows)
    return {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "python_version": platform.python_version(),
        "prompt_version": PromptStore().version,
        "dataset_sha256": hashlib.sha256(
            json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "mode": settings.provider,
        "model": settings.model,
        "cases": count,
        "schema_validation_rate": sum(r["schema_valid"] for r in rows) / count,
        "call_validation_success_rate": valid_calls / call_count if call_count else None,
        "required_field_accuracy": correct_fields / total_fields if total_fields else None,
        "correct_fields": correct_fields,
        "total_fields": total_fields,
        "type_accuracy": sum(r["actual_type"] == r["expected_type"] for r in rows) / count,
        "unsupported_claim_rate": unsupported / claim_count if claim_count else None,
        "unsupported_claims": unsupported,
        "claim_count": claim_count,
        "rejected_unsupported_attempts": rejected_claims,
        "model_calls": call_count,
        "p50_latency_ms": percentile([r["latency_ms"] for r in rows], 0.5),
        "p95_latency_ms": percentile([r["latency_ms"] for r in rows], 0.95),
        "expectations_met": sum(r["expectation_met"] for r in rows),
        "note": (
            "Mock/fault-fixture metrics are workflow checks, not real LLM accuracy. "
            "Gold labels have not received independent human review."
        ),
        "rows": rows,
    }


def write_results(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result["rows"][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result["rows"])
    summary = [
        "# Evaluation results",
        "",
        f"Mode: **{result['mode']}**; model: `{result['model']}`.",
        "",
        result["note"],
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    summary += [
        f"| {key} | {value} |" for key, value in result.items() if key not in {"rows", "note"}
    ]
    summary += [
        "",
        "See eval/README.md for denominators and the deliberate valid-schema misclassification.",
        "",
    ]
    (output / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/eval"))
    parser.add_argument("--require-expectations", action="store_true")
    args = parser.parse_args()
    settings = Settings(cache_enabled=False)
    cases = json.loads((ROOT / "eval/cases.json").read_text(encoding="utf-8"))
    result = evaluate(cases, settings)
    write_results(result, args.output)
    print(
        json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2)
    )
    return int(args.require_expectations and result["expectations_met"] != len(cases))


if __name__ == "__main__":
    raise SystemExit(main())
