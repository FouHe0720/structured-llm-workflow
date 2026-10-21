import json

import pytest

from app.adapters.mock import MockLLM
from app.api import create_app
from app.domain.errors import WorkflowError
from app.domain.models import Classification
from app.domain.provider import Completion
from app.infra.config import Settings
from app.infra.metrics import PriceTable
from app.services.model_service import ModelService
from app.services.pipeline import Pipeline


def test_empty_extractive_summary_is_valid():
    class EmptySummary(MockLLM):
        def complete(self, request):
            if request.step == "summarize":
                return Completion('{"sentences":[]}')
            return super().complete(request)

    workflow = Pipeline(provider=EmptySummary())
    result = workflow.run(workflow.parser.parse_text("An unclassified note."))
    assert result.summary == ""


@pytest.mark.parametrize("data", [[], {"models": []}, {"models": {"mock-fixture-v1": 42}}])
def test_invalid_price_table_stays_unknown(tmp_path, data):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(data))
    service = ModelService(MockLLM(), Settings(_env_file=None))
    service.call("classify", "note", Classification)
    assert PriceTable(path).cost("mock-fixture-v1", service.records[0]) is None


def test_bad_cache_path_has_partial_diagnostics(tmp_path):
    path = tmp_path / "file"
    path.write_text("already a file")
    workflow = Pipeline(settings=Settings(cache_enabled=True, cache_dir=path, _env_file=None))
    with pytest.raises(WorkflowError) as raised:
        workflow.run(workflow.parser.parse_text("note"))
    assert raised.value.code == "cache_io_error"
    assert raised.value.partial["usage"]["calls"] == 1


def test_api_startup_config_error_never_formats_secrets(monkeypatch):
    monkeypatch.setenv("WORKFLOW_PROVIDER", "openai")
    monkeypatch.setenv("WORKFLOW_BASE_URL", "invalid")
    monkeypatch.setenv("WORKFLOW_API_KEY", "test-secret-must-not-be-formatted")
    with pytest.raises(RuntimeError) as raised:
        create_app()
    assert "test-secret" not in str(raised.value)
    assert raised.value.__suppress_context__
