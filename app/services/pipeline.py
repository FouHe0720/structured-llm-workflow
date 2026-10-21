"""Fixed, typed orchestration with validated boundaries and partial diagnostics."""

import time

from pydantic import ValidationError

from app.adapters.mock import MockLLM
from app.adapters.parser import Parser
from app.domain.errors import WorkflowError
from app.domain.models import (
    AnalysisReport,
    CallRecord,
    Classification,
    Document,
    Highlights,
    Metadata,
    Summary,
    Usage,
)
from app.services.grounding import evidence_for
from schema.model_registry import MODEL_REGISTRY


class Pipeline:
    def __init__(self, provider: MockLLM | None = None, parser: Parser | None = None) -> None:
        self.provider = provider or MockLLM()
        self.parser = parser or Parser()

    def run(self, document: Document) -> AnalysisReport:
        records = []
        timings = {}
        partial = {"completed_steps": ["parser"], "document_hash": document.sha256}

        def call(step, model):
            start = time.perf_counter()
            try:
                raw = self.provider.complete(step, document.text, model)
                value = model.model_validate_json(raw)
            except (ValidationError, ValueError) as exc:
                raise WorkflowError(
                    "invalid_model_output", "Model output failed schema validation", step=step
                ) from exc
            elapsed = (time.perf_counter() - start) * 1000
            timings[step] = elapsed
            records.append(
                CallRecord(
                    step=step,
                    model=self.provider.model,
                    elapsed_ms=elapsed,
                    input_tokens=len(document.text),
                    output_tokens=len(raw),
                    token_source="estimated",
                    success=True,
                )
            )
            partial["completed_steps"].append(step)
            return value

        started = time.perf_counter()
        try:
            classification = call("classifier", Classification)
            extracted = call("extractor", MODEL_REGISTRY[classification.type])
            highlights = call("analyzer", Highlights)
            summary = call("summarizer", Summary)
            evidence = evidence_for(document, extracted.model_dump(), "extracted")
            evidence += evidence_for(document, highlights.model_dump(), "risks_or_highlights")
            evidence += evidence_for(document, summary.sentences, "summary")
            partial["completed_steps"].append("validator")
            timings["total_ms"] = (time.perf_counter() - started) * 1000
            latencies = sorted(r.elapsed_ms for r in records)
            return AnalysisReport(
                type=classification.type,
                metadata=Metadata(
                    name=document.name,
                    sha256=document.sha256,
                    characters=len(document.text),
                    pages=document.pages,
                    chunks=1,
                ),
                extracted=extracted,
                summary="\n".join(summary.sentences),
                risks_or_highlights=highlights,
                evidence=evidence,
                conflicts=[],
                model_info={
                    "provider": "mock",
                    "model": self.provider.model,
                    "prompt_version": "v0",
                },
                timings=timings,
                usage=Usage(
                    calls=len(records),
                    cache_hits=0,
                    input_tokens=sum(r.input_tokens for r in records),
                    output_tokens=sum(r.output_tokens for r in records),
                    token_source="estimated",
                    cost_usd=None,
                    validation_success_rate=1.0,
                    p50_ms=latencies[len(latencies) // 2],
                    p95_ms=latencies[-1],
                    records=records,
                ),
                validation_status="passed",
                warnings=document.warnings + ["Mock fixture results; not real model quality."],
            )
        except WorkflowError as exc:
            exc.partial = partial
            raise
