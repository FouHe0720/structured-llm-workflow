"""Versioned templates are packaged alongside code; raw documents stay in user data."""

import hashlib
import json
from importlib.resources import files

from app.domain.models import StrictModel
from app.domain.provider import ModelRequest


class PromptStore:
    def __init__(self) -> None:
        self.templates = {
            p.name.removesuffix(".md"): p.read_text(encoding="utf-8")
            for p in files("prompts").iterdir()
            if p.name.endswith(".md")
        }
        material = json.dumps(self.templates, sort_keys=True, ensure_ascii=False)
        self.version = "v1-" + hashlib.sha256(material.encode()).hexdigest()[:12]

    def request(
        self, step: str, source: str, schema: type[StrictModel], *, repair: bool = False
    ) -> ModelRequest:
        template = self.templates[step]
        system, user = template.split("\n## User\n", 1)
        # JSON string encoding makes delimiters in untrusted documents unambiguous.
        user += "\nUNTRUSTED_DOCUMENT_JSON=" + json.dumps(source, ensure_ascii=False)
        user += "\nOUTPUT_JSON_SCHEMA=" + json.dumps(schema.model_json_schema(), ensure_ascii=False)
        if repair:
            user += (
                "\nPrevious response failed validation. Return one COMPLETE JSON object matching "
                "the schema. Use only verbatim source spans; null/[] for missing facts."
            )
        return ModelRequest(step, source, schema, system, user, self.version)
