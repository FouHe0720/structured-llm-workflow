"""Real localhost sockets against a fixture endpoint, with zero external model calls."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.adapters.mock import MockLLM
from app.domain.models import AnalysisInsights, Classification, JobInfo, Summary
from app.domain.provider import ModelRequest
from app.infra.config import Settings
from app.services.pipeline import Pipeline


def test_compatible_provider_end_to_end_on_real_localhost_socket():
    schemas = {s.__name__: s for s in (Classification, JobInfo, AnalysisInsights, Summary)}
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(body)
            schema = schemas[body["response_format"]["json_schema"]["name"]]
            source = json.loads(
                body["messages"][1]["content"]
                .split("UNTRUSTED_DOCUMENT_JSON=", 1)[1]
                .split("\nOUTPUT_JSON_SCHEMA=", 1)[0]
            )
            reply = MockLLM().complete(ModelRequest("fixture", source, schema, "", "", "fixture"))
            data = json.dumps(
                {
                    "choices": [{"message": {"content": reply.content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        settings = Settings(
            provider="openai",
            model="localhost-fixture",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            _env_file=None,
        )
        pipeline = Pipeline(settings=settings)
        report = pipeline.run(
            pipeline.parser.parse_text("Job Description\nPosition: Reviewer\nSkills: Python")
        )
        assert report.extracted.position == "Reviewer"
        assert report.usage.calls == len(calls) == 4
        assert report.usage.token_source == "provider"
        assert report.model_info["model"] == "localhost-fixture"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
