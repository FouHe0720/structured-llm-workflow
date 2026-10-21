"""Errors deliberately omit provider bodies, credentials, and local absolute paths."""

from typing import Any


class WorkflowError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        step: str = "parser",
        partial: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.step = step
        self.partial = partial or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "step": self.step,
            "partial": self.partial,
        }
