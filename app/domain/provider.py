"""Provider boundary, independent of HTTP or fixture implementation."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.models import StrictModel


@dataclass(frozen=True)
class ModelRequest:
    step: str
    source: str
    schema: type[StrictModel]
    system: str
    user: str
    prompt_version: str
    max_output_tokens: int = 2048


@dataclass(frozen=True)
class Completion:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class Provider(Protocol):
    model: str

    def complete(self, request: ModelRequest) -> Completion: ...
