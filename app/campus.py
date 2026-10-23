"""Reproducible campus admission intake; no dates are silently normalized."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from app.domain.errors import WorkflowError
from app.services.campus_review import admission_review, review_markdown
from app.services.exporter import atomic_write
from app.services.pipeline import Pipeline

DEFAULT_MANIFEST = Path(__file__).resolve().parent / "fixtures/campus/manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="历史招生材料提取与审阅")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-id", default="navigation-admission-2024")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/campus-review.json"))
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        source = next((item for item in data["documents"] if item["id"] == args.source_id), None)
        if source is None:
            raise WorkflowError("unknown_source", "Source ID is not present in the manifest")
        source_path = args.manifest.parent / source["file_name"]
        destinations = (args.output.resolve(), args.output.with_suffix(".md").resolve())
        if args.output.suffix != ".json":
            raise WorkflowError("invalid_output", "Output path must end with .json")
        protected = {args.manifest.resolve()} | {
            (args.manifest.parent / item["file_name"]).resolve() for item in data["documents"]
        }
        if protected.intersection(destinations):
            raise WorkflowError("output_conflict", "Output must not overwrite source materials")
        report = Pipeline().analyze_file(source_path)
        packet = admission_review(report, source, args.as_of)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(args.output, json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
        atomic_write(args.output.with_suffix(".md"), review_markdown(packet))
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": type(exc).__name__}), file=sys.stderr)
        return 1
    except WorkflowError as exc:
        print(json.dumps({"error": exc.as_dict()}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": packet["status"],
                "issues": len(packet["issues"]),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
