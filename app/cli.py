"""CLI: python -m app.cli analyze examples/jd.txt --output outputs/jd.json."""

import argparse
import json
import sys
from pathlib import Path

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
    pipeline = Pipeline()
    try:
        document = pipeline.parser.parse_file(args.input)
        result = pipeline.run(document)
        export(result, args.output)
    except WorkflowError as exc:
        print(json.dumps({"error": exc.as_dict()}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"type": result.type.value, "output": str(args.output), "status": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
