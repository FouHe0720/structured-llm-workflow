import json
import subprocess
import sys

import pytest

from app.services.exporter import markdown
from app.services.model_service import extract_json
from app.services.pipeline import Pipeline


def test_duplicate_json_keys_are_not_silently_dropped():
    with pytest.raises(ValueError, match="Duplicate"):
        extract_json('{"type":"unknown", "type":"job_description"}')
    assert json.loads(extract_json('```json\n{"type":"unknown"}\n```')) == {"type": "unknown"}


def test_markdown_escapes_source_html_and_fences():
    workflow = Pipeline()
    report = workflow.run(
        workflow.parser.parse_text(
            "Job Description\nPosition: <script>bad</script>\nSummary: ``` injected fence"
        )
    )
    output = markdown(report)
    assert "\\<script\\>" in output
    assert "````json" in output


def test_cli_never_overwrites_input_or_uses_colliding_extensions(tmp_path):
    source = tmp_path / "input.md"
    original = "Job Description\nPosition: Reviewer"
    source.write_text(original)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "analyze",
            str(source),
            "--output",
            str(source.with_suffix(".json")),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stderr)["error"]["code"] == "output_conflict"
    assert source.read_text() == original
