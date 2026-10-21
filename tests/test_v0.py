import json
from pathlib import Path

import pytest

from app.adapters.parser import Parser
from app.domain.errors import WorkflowError
from app.domain.models import DocumentType
from app.services.exporter import export
from app.services.pipeline import Pipeline


def test_offline_jd_and_export(tmp_path):
    pipeline = Pipeline()
    document = pipeline.parser.parse_file(Path("examples/jd.txt"))
    report = pipeline.run(document)
    assert report.type == DocumentType.JOB
    assert report.extracted.experience is None
    assert report.extracted.skills == ["Python", "SQL", "Pydantic"]
    for evidence in report.evidence:
        assert document.text[evidence.start : evidence.end] == evidence.quote
    output = tmp_path / "report.json"
    export(report, output)
    assert json.loads(output.read_text())["validation_status"] == "passed"
    assert output.with_suffix(".md").exists()


@pytest.mark.parametrize("value", ["", "   ", "binary\x00"])
def test_bad_text(value):
    with pytest.raises(WorkflowError):
        Parser().parse_text(value)


def test_unknown_stays_empty():
    pipeline = Pipeline()
    result = pipeline.run(pipeline.parser.parse_text("A small fictional note."))
    assert result.type == DocumentType.UNKNOWN
    assert result.extracted.summary is None
