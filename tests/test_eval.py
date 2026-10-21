import json
from pathlib import Path

from app.infra.config import Settings
from eval.run_eval import evaluate, write_results


def test_annotated_evaluation_detects_errors_and_exports(tmp_path):
    cases = json.loads(Path("eval/cases.json").read_text(encoding="utf-8"))
    assert len(cases) == 40
    assert len({case["id"] for case in cases}) == 40
    result = evaluate(cases, Settings(_env_file=None))
    rows = {row["id"]: row for row in result["rows"]}
    assert rows["pa07"]["schema_valid"] is True
    assert rows["pa07"]["expectation_met"] is False
    assert rows["mm08"]["error"] == "llm_timeout"
    assert rows["un07"]["error"] == "unsupported_claim"
    assert rows["un08"]["error"] == "invalid_model_output"
    assert result["expectations_met"] == 39
    assert result["unsupported_claim_rate"] == 0
    write_results(result, tmp_path)
    assert json.loads((tmp_path / "results.json").read_text())["cases"] == 40
    assert len((tmp_path / "results.csv").read_text().splitlines()) == 41
    assert "mock" in (tmp_path / "SUMMARY.md").read_text()
