"""CLI: python -m app.cli analyze examples/jd.txt --output outputs/jd.json."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.domain.errors import WorkflowError
from app.services.exporter import export
from app.services.pipeline import Pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Structured LLM Workflow (offline Mock by default)"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("--output", type=Path, default=Path("outputs/report.json"))
    args = parser.parse_args()
    try:
        pipeline = Pipeline()
        result = pipeline.analyze_file(args.input)
        export(result, args.output)
    except ValidationError:
        print(
            json.dumps(
                {"error": {"code": "invalid_config", "message": "Check WORKFLOW_* settings"}}
            ),
            file=sys.stderr,
        )
        return 1
    except OSError:
        print(
            json.dumps({"error": {"code": "export_error", "message": "Cannot write output files"}}),
            file=sys.stderr,
        )
        return 1
    except WorkflowError as exc:
        print(json.dumps({"error": exc.as_dict()}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"type": result.type.value, "output": str(args.output), "status": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
