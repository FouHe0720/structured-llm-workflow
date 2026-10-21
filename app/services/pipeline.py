"""Fixed typed workflow; model services and diagnostics are isolated per run."""

import time
from pathlib import Path
from typing import TypeVar

from app.adapters.mock import MockLLM
from app.adapters.openai_compatible import OpenAICompatible
from app.adapters.parser import Parser
from app.domain.errors import WorkflowError
from app.domain.models import (
    AnalysisInsights,
    AnalysisReport,
    Classification,
    Conflict,
    Document,
    DocumentType,
    Highlights,
    Metadata,
    StrictModel,
    Summary,
)
from app.domain.provider import Provider
from app.infra.config import Settings
from app.infra.metrics import aggregate, conservative_tokens
from app.services.chunking import chunks
from app.services.grounding import evidence_for
from app.services.merge import merge_extractions
from app.services.model_service import ModelService
from schema.model_registry import MODEL_REGISTRY

T = TypeVar("T", bound=StrictModel)


class Pipeline:
    def __init__(
        self,
        provider: Provider | None = None,
        parser: Parser | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.provider = provider or (
            MockLLM() if self.settings.provider == "mock" else OpenAICompatible(self.settings)
        )
        self.parser = parser or Parser(
            self.settings.max_bytes, self.settings.max_chars, self.settings.max_pages
        )

    def analyze_file(self, path: Path) -> AnalysisReport:
        start = time.perf_counter()
        document = self.parser.parse_file(path)
        parser_ms = (time.perf_counter() - start) * 1000
        report = self.run(document)
        report.timings["parser_ms"] = parser_ms
        report.timings["total_ms"] += parser_ms
        return report

    def run(self, document: Document) -> AnalysisReport:
        started = time.perf_counter()
        service = ModelService(self.provider, self.settings, document.sha256)
        timings: dict[str, float] = {}
        partial: dict = {"completed_steps": ["parser"], "document_hash": document.sha256}
        warnings = list(document.warnings)
        source_chunks = chunks(document.text, self.settings.chunk_tokens)
        if any(
            conservative_tokens(line) > self.settings.chunk_tokens
            for line in document.text.splitlines()
        ):
            warnings.append(
                "An over-budget line was split; relationships spanning chunks "
                "may need human review."
            )
        if len(source_chunks) > 1:
            warnings.append(
                f"Map/Reduce over {len(source_chunks)} chunks; UTF-8 byte estimates are "
                "not actual tokens. No source text was truncated."
            )

        def call(step: str, source: str, schema: type[T]) -> T:
            start = time.perf_counter()
            result = service.call(step, source, schema)
            timings[step + "_ms"] = (
                timings.get(step + "_ms", 0) + (time.perf_counter() - start) * 1000
            )
            return result

        try:
            classifications = [call("classify", c, Classification).type for c in source_chunks]
            known = set(classifications) - {DocumentType.UNKNOWN}
            document_type = next(iter(known)) if len(known) == 1 else DocumentType.UNKNOWN
            if len(known) > 1:
                warnings.append("Conflicting chunk classifications; document type remains unknown.")
            partial["completed_steps"].append("classifier")
            partial["type"] = document_type.value
            schema = MODEL_REGISTRY[document_type]
            mapped = [call("extract_" + document_type.value, c, schema) for c in source_chunks]
            extracted, conflicts = merge_extractions(mapped, schema)
            partial["completed_steps"].append("extractor")
            partial["extracted"] = extracted.model_dump()
            insights = [call("analyze", c, AnalysisInsights) for c in source_chunks]
            highlights = Highlights(
                highlights=list(dict.fromkeys(h for v in insights for h in v.highlights)),
                risks=list(dict.fromkeys(r for v in insights for r in v.risks)),
            )
            conflict_values: dict[str, list[str]] = {}
            for conflict in conflicts + [c for v in insights for c in v.conflicts]:
                conflict_values.setdefault(conflict.field, []).extend(conflict.values)
            conflicts = [
                Conflict(field=field, values=list(dict.fromkeys(values)))
                for field, values in conflict_values.items()
                if len(set(values)) > 1
            ]
            payload = extracted.model_dump()
            for conflict in conflicts:
                if conflict.field in payload:
                    payload[conflict.field] = None
            extracted = schema.model_validate(payload)
            partial["extracted"] = payload
            partial["completed_steps"].append("analyzer")
            mapped_summaries = [call("summarize", c, Summary) for c in source_chunks]
            sentences = list(dict.fromkeys(s for v in mapped_summaries for s in v.sentences))
            if len(source_chunks) > 1 and sentences:
                combined = "\n".join(sentences)
                while conservative_tokens(combined) > self.settings.chunk_tokens:
                    reduced = [
                        call("reduce", c, Summary)
                        for c in chunks(combined, self.settings.chunk_tokens)
                    ]
                    next_text = "\n".join(dict.fromkeys(s for v in reduced for s in v.sentences))
                    if conservative_tokens(next_text) >= conservative_tokens(combined):
                        raise WorkflowError(
                            "reduce_not_converging",
                            "Summary reducer failed to shrink content",
                            step="summarizer",
                        )
                    combined = next_text
                sentences = call("reduce", combined, Summary).sentences
            partial["completed_steps"].append("summarizer")
            start = time.perf_counter()
            evidence = evidence_for(document, extracted.model_dump(), "extracted")
            evidence += evidence_for(document, highlights.model_dump(), "risks_or_highlights")
            evidence += evidence_for(document, sentences, "summary")
            evidence += evidence_for(document, [c.values for c in conflicts], "conflicts")
            timings["validator_ms"] = (time.perf_counter() - start) * 1000
            partial["completed_steps"].append("validator")
            if conflicts:
                warnings.append(
                    "Conflicting scalar facts retained; affected extracted fields are null."
                )
            if self.settings.provider == "mock":
                warnings.append("Mock fixture/label simulator results; not real model quality.")
            timings["total_ms"] = (time.perf_counter() - started) * 1000
            return AnalysisReport(
                type=document_type,
                metadata=Metadata(
                    name=document.name,
                    sha256=document.sha256,
                    characters=len(document.text),
                    pages=document.pages,
                    chunks=len(source_chunks),
                ),
                extracted=extracted,
                summary="\n".join(sentences),
                risks_or_highlights=highlights,
                evidence=evidence,
                conflicts=conflicts,
                model_info={
                    "provider": self.settings.provider,
                    "model": self.provider.model,
                    "prompt_version": service.prompts.version,
                    "response_mode": self.settings.response_mode,
                },
                timings=timings,
                usage=aggregate(service.records),
                validation_status="passed",
                warnings=warnings,
            )
        except WorkflowError as exc:
            partial["usage"] = aggregate(service.records).model_dump()
            exc.partial = partial
            raise
