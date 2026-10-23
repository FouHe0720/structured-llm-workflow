PYTHON ?= .venv/bin/python
RUFF := .venv/bin/ruff

.PHONY: install test lint format demo campus-demo eval serve check
install:
	@if command -v uv >/dev/null 2>&1; then uv sync --extra dev --frozen; else python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'; fi
test:
	$(PYTHON) -m pytest -q
lint:
	$(RUFF) check .
	$(RUFF) format --check .
format:
	$(RUFF) check --fix .
	$(RUFF) format .
demo:
	$(PYTHON) -m examples.generate
	$(PYTHON) -m app.cli analyze examples/jd.txt --output outputs/jd.json
	$(PYTHON) -m app.cli analyze examples/sample.pdf --output outputs/pdf.json
	$(PYTHON) -m app.cli analyze examples/long_50000.txt --output outputs/long.json
campus-demo:
	$(PYTHON) -m app.campus --source-id navigation-admission-2024 --as-of 2026-10-23 --output outputs/campus/navigation.json
	$(PYTHON) -m app.campus --source-id computational-law-admission-2024 --as-of 2026-10-23 --output outputs/campus/law.json
eval:
	$(PYTHON) -m eval.run_eval --output outputs/eval
serve:
	$(PYTHON) -m app.api
check: lint test
