"""Fixture/label-driven simulator, not an NLP model; never executes document instructions."""

import json
import re
from importlib.resources import files

from app.domain.models import Classification, DocumentType, Highlights, StrictModel, Summary


class MockLLM:
    model = "mock-fixture-v1"

    def __init__(self) -> None:
        self.rules = json.loads(
            files("app.adapters").joinpath("fixtures/mock_rules.json").read_text(encoding="utf-8")
        )

    def complete(self, step: str, text: str, schema: type[StrictModel]) -> str:
        if schema is Classification:
            matches = [
                key
                for key, markers in self.rules["types"].items()
                if any(marker.casefold() in text.casefold() for marker in markers)
            ]
            return json.dumps({"type": matches[0] if len(matches) == 1 else DocumentType.UNKNOWN})
        if schema is Highlights:
            risks = self._values(text, ["Risk", "风险", "Limitations", "局限"])
            return json.dumps({"highlights": [], "risks": risks}, ensure_ascii=False)
        if schema is Summary:
            values = self._values(text, ["Summary", "摘要"])
            if not values:
                values = [line.strip() for line in text.splitlines() if line.strip()][:1]
            return json.dumps({"sentences": list(dict.fromkeys(values))[:3]}, ensure_ascii=False)
        result: dict = {}
        for field in schema.model_fields:
            values = self._values(text, self.rules["fields"][field])
            if field in self.rules["lists"]:
                values = [
                    v.strip() for value in values for v in re.split(r"[;；]", value) if v.strip()
                ]
                result[field] = list(dict.fromkeys(values))
            else:
                result[field] = values[0] if values else None
        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _values(text: str, labels: list[str]) -> list[str]:
        pattern = r"^(?:" + "|".join(map(re.escape, labels)) + r")[ \t]*[:：][ \t]*(.+)$"
        return [m.group(1).strip() for m in re.finditer(pattern, text, flags=re.M | re.I)]
