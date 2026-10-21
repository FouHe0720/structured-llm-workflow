"""Fixture/label-driven simulator, not an NLP model; never executes document instructions."""

import json
import re
from importlib.resources import files

from app.domain.models import AnalysisInsights, Classification, DocumentType, Summary
from app.domain.provider import Completion, ModelRequest


class MockLLM:
    model = "mock-fixture-v1"

    def __init__(self) -> None:
        self.rules = json.loads(
            files("app.adapters").joinpath("fixtures/mock_rules.json").read_text(encoding="utf-8")
        )

    def complete(self, request: ModelRequest) -> Completion:
        return Completion(self._content(request))

    def _content(self, request: ModelRequest) -> str:
        text, schema = request.source, request.schema
        if schema is Classification:
            matches = [
                key
                for key, markers in self.rules["types"].items()
                if any(marker.casefold() in text.casefold() for marker in markers)
            ]
            return json.dumps({"type": matches[0] if len(matches) == 1 else DocumentType.UNKNOWN})
        if schema is AnalysisInsights:
            risks = self._values(text, ["Risk", "风险", "Limitations", "局限"])
            conflicts = []
            for field, labels in self.rules["fields"].items():
                if field not in self.rules["lists"]:
                    values = list(dict.fromkeys(self._values(text, labels)))
                    if len(values) > 1:
                        conflicts.append({"field": field, "values": values})
            return json.dumps(
                {"highlights": [], "risks": risks, "conflicts": conflicts}, ensure_ascii=False
            )
        if schema is Summary:
            if request.step == "reduce":
                return json.dumps(
                    {"sentences": self._brief(list(dict.fromkeys(text.splitlines())))},
                    ensure_ascii=False,
                )
            values = self._values(text, ["Summary", "摘要"])
            if not values:
                values = [line.strip() for line in text.splitlines() if line.strip()][:1]
            return json.dumps(
                {"sentences": self._brief(list(dict.fromkeys(values)))}, ensure_ascii=False
            )
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
    def _brief(values: list[str]) -> list[str]:
        remaining = 192
        result = []
        for value in values[:3]:
            clipped = value.encode("utf-8")[:remaining].decode("utf-8", errors="ignore")
            if clipped:
                result.append(clipped)
                remaining -= len(clipped.encode("utf-8"))
        return result

    @staticmethod
    def _values(text: str, labels: list[str]) -> list[str]:
        pattern = r"^(?:" + "|".join(map(re.escape, labels)) + r")[ \t]*[:：][ \t]*(.+)$"
        return [m.group(1).strip() for m in re.finditer(pattern, text, flags=re.M | re.I)]
