"""Minimal Chat Completions transport with explicit schema capability selection."""

import httpx

from app.domain.errors import WorkflowError
from app.domain.provider import Completion, ModelRequest
from app.infra.config import Settings


class OpenAICompatible:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.model = settings.model
        self.transport = transport

    def complete(self, request: ModelRequest) -> Completion:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_output_tokens,
        }
        if self.settings.response_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema.__name__,
                    "strict": True,
                    "schema": request.schema.model_json_schema(),
                },
            }
        elif self.settings.response_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
        headers = {"Accept": "application/json"}
        key = self.settings.api_key.get_secret_value()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            with httpx.Client(
                timeout=self.settings.timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    self.settings.base_url.rstrip("/") + "/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if response.status_code >= 300:
                    raise WorkflowError(
                        f"provider_http_{response.status_code}",
                        "Provider rejected request; check endpoint, credentials, model and "
                        "WORKFLOW_RESPONSE_MODE. Provider response body is withheld.",
                        step=request.step,
                    )
                if len(response.content) > 1_048_576:
                    raise WorkflowError(
                        "provider_response_too_large",
                        "Provider response exceeds 1 MiB",
                        step=request.step,
                    )
                body = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise WorkflowError(
                        "output_truncated", "Provider reached output token limit", step=request.step
                    )
                if choice["message"].get("refusal"):
                    raise WorkflowError(
                        "model_refusal", "Provider refused request", step=request.step
                    )
                content = choice["message"]["content"]
                if not isinstance(content, str):
                    raise ValueError("Missing string content")
                usage = body.get("usage") or {}
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")
                if not all(type(n) is int and n >= 0 for n in (input_tokens, output_tokens)):
                    input_tokens = output_tokens = None
                return Completion(content, input_tokens, output_tokens)
        except httpx.TimeoutException as exc:
            raise WorkflowError(
                "llm_timeout", "Model request timed out", step=request.step
            ) from exc
        except httpx.HTTPError as exc:
            raise WorkflowError(
                "provider_connection", "Cannot connect to model provider", step=request.step
            ) from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise WorkflowError(
                "provider_protocol", "Unexpected provider response structure", step=request.step
            ) from exc
