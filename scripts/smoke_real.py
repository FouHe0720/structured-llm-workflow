"""Opt-in network verification. Only run after configuring WORKFLOW_PROVIDER=openai."""

import json
from pathlib import Path

from app.infra.config import Settings
from app.services.exporter import export
from app.services.pipeline import Pipeline


def main() -> None:
    settings = Settings()
    if settings.provider != "openai":
        raise SystemExit("Set WORKFLOW_PROVIDER=openai and configure endpoint/model first.")
    workflow = Pipeline(settings=settings)
    report = workflow.run(
        workflow.parser.parse_text(
            "Job Description\nPosition: Workflow Reviewer\nSkills: Python\n"
            "Summary: Review source evidence."
        )
    )
    export(report, Path("outputs/real-smoke.json"))
    print(
        json.dumps(
            {
                "provider": report.model_info["provider"],
                "model": report.model_info["model"],
                "schema": report.validation_status,
                "calls": report.usage.calls,
                "note": "This verifies one request path; it is not a quality benchmark.",
            }
        )
    )


if __name__ == "__main__":
    main()
