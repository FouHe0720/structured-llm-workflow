"""JSON extraction, strict Pydantic validation, bounded repairs and per-attempt telemetry."""

import json
import time
from typing import TypeVar

from pydantic import ValidationError

from app.domain.errors import WorkflowError
from app.domain.models import AnalysisInsights, CallRecord, Classification, StrictModel, Summary
from app.domain.provider import Provider
from app.infra.cache import LocalCache
from app.infra.config import Settings
from app.infra.metrics import PriceTable, conservative_tokens
from app.infra.prompts import PromptStore
from app.services.grounding import claims

T = TypeVar("T", bound=StrictModel)


def extract_json(raw: str) -> str:
    """Accept a single complete JSON object, optionally surrounded by a Markdown fence."""
    raw = raw.strip()
    if raw.startswith("```") and raw.endswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return json.dumps(value, ensure_ascii=False)


class ModelService:
    def __init__(self, provider: Provider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings
        self.prompts = PromptStore()
        self.cache = LocalCache(settings.cache_dir, settings.cache_enabled)
        self.prices = PriceTable(settings.price_file)
        self.records: list[CallRecord] = []
        # Endpoint identity is hashed into the namespace; credentials are never included.
        self.namespace = "|".join(
            (settings.provider, provider.model, settings.base_url, settings.response_mode)
        )

    @staticmethod
    def validate(raw: str, schema: type[T], source: str) -> T:
        value = schema.model_validate_json(extract_json(raw))
        if schema is Summary and (
            len(value.sentences) > 3 or sum(conservative_tokens(s) for s in value.sentences) > 192
        ):
            raise ValueError("Extractive summary exceeds three spans / 192 estimated tokens")
        if schema is not Classification:
            payload = value.model_dump()
            if schema is AnalysisInsights:
                payload["conflicts"] = [c.values for c in value.conflicts]
            for _, claim in claims(payload):
                if claim not in source:
                    raise WorkflowError("unsupported_claim", "Claim lacks verbatim source support")
        return value

    def call(self, step: str, source: str, schema: type[T]) -> T:
        request = self.prompts.request(step, source, schema)
        key = self.cache.key(request, self.namespace)
        cached = self.cache.get(key)
        if cached is not None:
            try:
                value = self.validate(cached, schema, source)
                self.records.append(
                    CallRecord(
                        step=step,
                        model=self.provider.model,
                        elapsed_ms=0.0,
                        input_tokens=0,
                        output_tokens=0,
                        token_source="cache",
                        success=True,
                        cache_hit=True,
                        cost_usd=0.0,
                    )
                )
                return value
            except (ValueError, ValidationError, WorkflowError):
                pass  # Corrupt/stale cache entries are misses, never trusted reports.
        for attempt in range(self.settings.max_repairs + 1):
            if sum(not r.cache_hit for r in self.records) >= self.settings.max_calls:
                raise WorkflowError(
                    "call_budget_exceeded", "Model call budget exhausted", step=step
                )
            request = self.prompts.request(step, source, schema, repair=attempt > 0)
            if (
                conservative_tokens(request.system + request.user) + request.max_output_tokens
                > self.settings.context_tokens
            ):
                raise WorkflowError(
                    "context_budget_exceeded",
                    "Prompt, schema and output reserve exceed "
                    "configured context budget; reduce chunk size or increase context budget",
                    step=step,
                )
            started = time.perf_counter()
            record = CallRecord(
                step=step,
                model=self.provider.model,
                elapsed_ms=0.0,
                input_tokens=conservative_tokens(request.system + request.user),
                output_tokens=0,
                token_source="estimated",
                success=False,
            )
            try:
                reply = self.provider.complete(request)
                record.output_tokens = conservative_tokens(reply.content)
                if reply.input_tokens is not None and reply.output_tokens is not None:
                    record.input_tokens = reply.input_tokens
                    record.output_tokens = reply.output_tokens
                    record.token_source = "provider"
                value = self.validate(reply.content, schema, source)
                record.success = True
            except (ValueError, ValidationError) as exc:
                record.error_code = "invalid_model_output"
                if attempt >= self.settings.max_repairs:
                    raise WorkflowError(
                        "invalid_model_output",
                        "Model output failed JSON/Pydantic validation after bounded repair",
                        step=step,
                    ) from exc
                continue
            except WorkflowError as exc:
                record.error_code = exc.code
                exc.step = step
                if exc.code == "unsupported_claim" and attempt < self.settings.max_repairs:
                    continue
                raise
            finally:
                record.elapsed_ms = (time.perf_counter() - started) * 1000
                record.cost_usd = self.prices.cost(self.provider.model, record)
                self.records.append(record)
            self.cache.put(key, value.model_dump_json())
            return value
        raise AssertionError("Unreachable bounded repair loop")
