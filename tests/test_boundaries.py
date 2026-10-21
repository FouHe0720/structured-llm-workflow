import json
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.adapters.mock import MockLLM
from app.adapters.openai_compatible import OpenAICompatible
from app.adapters.parser import Parser
from app.api import create_app
from app.domain.errors import WorkflowError
from app.domain.models import Classification
from app.infra.config import Settings
from app.infra.metrics import PriceTable, aggregate
from app.infra.prompts import PromptStore
from app.services.model_service import ModelService
from app.services.pipeline import Pipeline
from examples.generate import text_pdf


def test_pdf_text_pages_and_evidence():
    data = text_pdf(
        ["Job Description\nPosition: PDF Reviewer", "Skills: Python\nSummary: Keep pages."]
    )
    workflow = Pipeline()
    document = workflow.parser.parse_bytes(data, "sample.pdf")
    report = workflow.run(document)
    assert document.pages == 2
    assert report.extracted.skills == ["Python"]
    assert next(e for e in report.evidence if e.quote == "Python").page == 2
    assert all(document.text[e.start : e.end] == e.quote for e in report.evidence)


@pytest.mark.parametrize(
    "data, code", [(b"bad pdf", "pdf_parse_error"), (text_pdf([""]), "ocr_not_supported")]
)
def test_invalid_or_scanned_pdf(data, code):
    with pytest.raises(WorkflowError) as raised:
        Parser().parse_bytes(data, "bad.pdf")
    assert raised.value.code == code


def test_pdf_blank_page_warning_and_page_limit():
    data = text_pdf(["Technical Report\nTitle: Demo", ""])
    assert "Page 2" in Parser().parse_bytes(data, "demo.pdf").warnings[0]
    with pytest.raises(WorkflowError) as raised:
        Parser(max_pages=1).parse_bytes(data, "demo.pdf")
    assert raised.value.code == "too_many_pages"


def test_encrypted_pdf_is_rejected():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("fictional-password")
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(WorkflowError) as raised:
        Parser().parse_bytes(stream.getvalue(), "locked.pdf")
    assert raised.value.code == "encrypted_pdf"


@pytest.mark.parametrize(
    "data,name,code",
    [
        (b"x" * 101, "a.txt", "file_too_large"),
        (b"text", "a.exe", "unsupported_type"),
        (b"\xff", "a.txt", "invalid_encoding"),
    ],
)
def test_parser_limits(data, name, code):
    with pytest.raises(WorkflowError) as raised:
        Parser(max_bytes=100).parse_bytes(data, name)
    assert raised.value.code == code


def test_api_text_upload_health_and_input_errors():
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["provider"] == "mock"
        response = client.post("/v1/analyze", json={"text": "Job Description\nPosition: Reviewer"})
        assert response.status_code == 200
        assert response.json()["extracted"]["position"] == "Reviewer"
        response = client.post(
            "/v1/analyze/file",
            files={"file": ("job.txt", b"Job Description\nSkills: SQL", "text/plain")},
        )
        assert response.status_code == 200
        assert response.json()["extracted"]["skills"] == ["SQL"]
        response = client.post("/v1/analyze", json={"text": "value", "extra": "test-secret"})
        assert response.status_code == 422
        assert "test-secret" not in response.text
        assert response.json()["error"]["code"] == "invalid_request"


def test_api_byte_limit_without_content_length():
    settings = Settings(max_bytes=100, _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/analyze", content=iter([b"x" * 70_000]))
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "body_too_large"
        response = client.post("/v1/analyze", json={"text": "x" * 101})
        assert response.status_code == 413


@pytest.mark.parametrize("mode", ["json_schema", "json_object", "text"])
def test_provider_protocol_modes_usage_and_no_key_leak(mode):
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer fixture-only-secret"
        if mode == "json_schema":
            fmt = payload["response_format"]
            assert fmt["json_schema"]["strict"] is True
            assert fmt["json_schema"]["schema"]["additionalProperties"] is False
        elif mode == "json_object":
            assert payload["response_format"] == {"type": "json_object"}
        else:
            assert "response_format" not in payload
        assert "fixture-only-secret" not in json.dumps(payload)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"type":"unknown"}'}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 5},
            },
        )

    settings = Settings(
        provider="openai",
        model="local-model",
        base_url="https://provider.example/v1",
        api_key="fixture-only-secret",
        response_mode=mode,
        _env_file=None,
    )
    service = ModelService(OpenAICompatible(settings, httpx.MockTransport(handler)), settings)
    service.call("classify", "A note", Classification)
    usage = aggregate(service.records)
    assert usage.input_tokens == 20 and usage.output_tokens == 5
    assert usage.token_source == "provider" and usage.cost_usd is None


@pytest.mark.parametrize("status", [401, 429, 500, 302])
def test_provider_http_errors_sanitized(status):
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text="private-provider-error"))
    settings = Settings(
        provider="openai", model="local-model", base_url="http://localhost:9999/v1", _env_file=None
    )
    provider = OpenAICompatible(settings, transport)
    with pytest.raises(WorkflowError) as raised:
        provider.complete(PromptStore().request("classify", "note", Classification))
    assert raised.value.code == f"provider_http_{status}"
    assert "private-provider-error" not in str(raised.value)


def test_provider_http_timeout_and_api_504():
    def timeout(_):
        raise httpx.ReadTimeout("fixture timeout with private detail")

    settings = Settings(
        provider="openai", model="local-model", base_url="http://localhost:9999/v1", _env_file=None
    )
    provider = OpenAICompatible(settings, httpx.MockTransport(timeout))
    workflow = Pipeline(provider=provider, settings=settings)
    with TestClient(create_app(settings, workflow)) as client:
        response = client.post("/v1/analyze", json={"text": "note"})
    assert response.status_code == 504
    assert response.json()["error"]["partial"]["usage"]["calls"] == 1
    assert "private detail" not in response.text


@pytest.mark.parametrize(
    "choice,code",
    [
        ({"message": {"refusal": "no"}}, "model_refusal"),
        ({"message": {"content": "{}"}, "finish_reason": "length"}, "output_truncated"),
        ({"message": {"content": None}}, "provider_protocol"),
    ],
)
def test_provider_refusal_truncation_protocol(choice, code):
    settings = Settings(
        provider="openai",
        model="local-model",
        base_url="https://provider.example/v1",
        _env_file=None,
    )
    provider = OpenAICompatible(
        settings, httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [choice]}))
    )
    with pytest.raises(WorkflowError) as raised:
        provider.complete(PromptStore().request("classify", "note", Classification))
    assert raised.value.code == code


def test_price_requires_source_and_date(tmp_path):
    service = ModelService(MockLLM(), Settings(_env_file=None))
    service.call("classify", "note", Classification)
    record = service.records[0]
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps(
            {
                "models": {
                    "mock-fixture-v1": {
                        "input_usd_per_million_tokens": 1,
                        "output_usd_per_million_tokens": 2,
                    }
                }
            }
        )
    )
    assert PriceTable(path).cost("mock-fixture-v1", record) is None
    path.write_text(
        json.dumps(
            {
                "models": {
                    "mock-fixture-v1": {
                        "as_of": "2026-01-01",
                        "source": "https://example.org/fictional-prices",
                        "input_usd_per_million_tokens": 1,
                        "output_usd_per_million_tokens": 2,
                    }
                }
            }
        )
    )
    assert (
        PriceTable(path).cost("mock-fixture-v1", record)
        == (record.input_tokens + 2 * record.output_tokens) / 1_000_000
    )
