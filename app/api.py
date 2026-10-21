"""Bounded ASGI ingress. JSON text + multipart file routes share one pipeline."""

import json
from typing import Annotated

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from app.domain.errors import WorkflowError
from app.infra.config import Settings
from app.services.pipeline import Pipeline


class BodyLimit:
    """Buffer at most the configured limit before JSON/multipart parsing, even without length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {"code": "body_too_large", "message": "Request exceeds byte limit"}
                    },
                )
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> dict:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=1_000_000)
    name: str = Field(default="input.txt", min_length=1, max_length=100)


def create_app(settings: Settings | None = None, pipeline: Pipeline | None = None) -> FastAPI:
    settings = settings or Settings()
    workflow = pipeline or Pipeline(settings=settings)
    api = FastAPI(title="Structured LLM Workflow", version="0.1.0")
    # Bounded allowance for JSON escape / multipart overhead; file/text checked again below.
    api.add_middleware(BodyLimit, max_bytes=settings.max_bytes + 65_536)

    @api.exception_handler(WorkflowError)
    async def workflow_error(_: Request, exc: WorkflowError) -> JSONResponse:
        status = 422
        if exc.code in {"file_too_large", "too_many_pages"}:
            status = 413
        elif exc.code == "llm_timeout":
            status = 504
        elif exc.step not in {"parser", "validator"}:
            status = 502
        return JSONResponse(status_code=status, content={"error": exc.as_dict()})

    @api.exception_handler(RequestValidationError)
    async def request_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": "invalid_request", "message": "Request violates input schema"}
            },
        )

    @api.get("/health")
    def health() -> dict:
        return {"status": "ok", "provider": settings.provider, "model": workflow.provider.model}

    @api.post("/v1/analyze")
    def analyze(body: AnalyzeRequest) -> dict:
        document = workflow.parser.parse_text(body.text, body.name)
        return workflow.run(document).model_dump(mode="json")

    @api.post("/v1/analyze/file")
    async def analyze_file(file: Annotated[UploadFile, File()]) -> dict:
        try:
            data = await file.read(settings.max_bytes + 1)
            document = await run_in_threadpool(
                workflow.parser.parse_bytes, data, file.filename or "input.txt"
            )
            report = await run_in_threadpool(workflow.run, document)
            return report.model_dump(mode="json")
        finally:
            await file.close()

    return api


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(create_app(), host="127.0.0.1", port=8000)
    except ValidationError:
        raise SystemExit(json.dumps({"error": "Invalid WORKFLOW_* settings"})) from None
