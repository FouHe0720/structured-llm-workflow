FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WORKFLOW_PROVIDER=mock
WORKDIR /workspace
COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock
COPY pyproject.toml LICENSE ./
COPY app/ app/
COPY schema/ schema/
COPY prompts/ prompts/
COPY config/ config/
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 workflow
COPY examples/ examples/
USER workflow
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "app.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
