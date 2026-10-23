"""Historical admissions retain exact wording and enter a review queue."""

import copy
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.domain.errors import WorkflowError
from app.domain.models import CampusAdmissionInfo
from app.services.campus_review import admission_review, review_markdown
from app.services.pipeline import Pipeline

DATA = Path(__file__).resolve().parents[1] / "app/fixtures/campus"
SOURCES = json.loads((DATA / "manifest.json").read_text())["documents"]


def packet_for(source_id: str) -> dict:
    source = next(item for item in SOURCES if item["id"] == source_id)
    report = Pipeline().analyze_file(DATA / source["file_name"])
    assert isinstance(report.extracted, CampusAdmissionInfo)
    return admission_review(report, source, date(2026, 10, 23))


def test_navigation_retains_ambiguous_time_and_qualification_exceptions() -> None:
    packet = packet_for("navigation-admission-2024")
    fields = packet["report"]["extracted"]
    assert "9月9日中午14点" in fields["registration_window"]
    assert "不允许转专业的不得报名" in fields["audience"]
    assert any("30名" in rule for rule in fields["quota_rules"])
    assert {issue["code"] for issue in packet["issues"]} == {"ambiguous_time", "historical_source"}
    assert packet["status"] == "needs_human_review"
    assert "待人工核对" in review_markdown(packet)


def test_law_does_not_turn_interview_shortlist_into_quota_or_infer_year() -> None:
    packet = packet_for("computational-law-admission-2024")
    fields = packet["report"]["extracted"]
    assert "截止到9月6号晚上7：00" in fields["registration_window"]
    assert "2024" not in fields["registration_window"]
    assert all("1∶1.2" not in rule for rule in fields["quota_rules"])
    assert any("1∶1.2" in rule for rule in fields["selection_rules"])
    assert "year_not_explicit" in {issue["code"] for issue in packet["issues"]}


@pytest.mark.parametrize("source", SOURCES, ids=lambda source: source["id"])
def test_bundled_hash_and_every_field_evidence_resolve_to_original_paragraph(source: dict) -> None:
    path = DATA / source["file_name"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["excerpt_sha256"]
    text = path.read_text()
    packet = packet_for(source["id"])
    original = {item["index"]: item["text"] for item in source["paragraphs"]}
    for evidence in packet["evidence"]:
        # Summary can quote the Markdown heading, which is editorial metadata.
        if evidence["field"].startswith("extracted."):
            assert evidence["quote"] in original[evidence["source_paragraph"]]
        assert text[evidence["start"] : evidence["end"]] == evidence["quote"]


def test_manifest_mismatch_blocks_review_and_missing_fields_are_visible() -> None:
    source = copy.deepcopy(SOURCES[0])
    workflow = Pipeline()
    report = workflow.run(workflow.parser.parse_text("2024级某实验班招生简章"))
    with pytest.raises(WorkflowError, match="Excerpt does not match"):
        admission_review(report, source, date(2026, 10, 23))
    source["excerpt_sha256"] = report.metadata.sha256
    packet = admission_review(report, source, date(2024, 9, 1))
    assert {item["field"] for item in packet["issues"] if item["code"] == "missing_field"} == {
        "audience",
        "registration_window",
        "quota_rules",
    }
    assert packet["status"] == "needs_human_review"


def test_cli_refuses_output_that_overwrites_manifest() -> None:
    manifest = DATA / "manifest.json"
    original = manifest.read_bytes()
    result = subprocess.run(
        [sys.executable, "-m", "app.campus", "--as-of", "2026-10-23", "--output", str(manifest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "output_conflict" in result.stderr
    assert manifest.read_bytes() == original


def test_different_quota_numbers_are_retained_for_review() -> None:
    workflow = Pipeline()
    report = workflow.run(
        workflow.parser.parse_text(
            "2024级某实验班招生简章\n实验班招生计划人数为30人。\n本班共录取25名。"
        )
    )
    source = copy.deepcopy(SOURCES[0])
    source["excerpt_sha256"] = report.metadata.sha256
    packet = admission_review(report, source, date(2024, 9, 1))
    assert "conflicting_quota" in {issue["code"] for issue in packet["issues"]}
    assert len(packet["report"]["extracted"]["quota_rules"]) == 2


def test_review_markdown_keeps_untrusted_text_out_of_table_structure() -> None:
    packet = packet_for("navigation-admission-2024")
    packet["report"]["extracted"]["title"] = "<script>unsafe</script>"
    packet["report"]["extracted"]["audience"] = "申请人 | 限制\n下一行"
    output = review_markdown(packet)
    assert "<script>" not in output
    assert "\\<script\\>" in output
    assert "申请人 \\| 限制<br>下一行" in output
    assert output.index("## 需要核对") < output.index("## 招生信息")
    assert packet["source"]["source_sha256"] in output
