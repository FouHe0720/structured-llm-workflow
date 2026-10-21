"""Opt-in, content-addressed local cache. Never cache invalid model outputs."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from app.domain.provider import ModelRequest


class LocalCache:
    def __init__(self, directory: Path, enabled: bool) -> None:
        self.directory = directory
        self.enabled = enabled

    @staticmethod
    def key(request: ModelRequest, namespace: str) -> str:
        material = {
            "namespace": namespace,
            "step": request.step,
            "prompt_version": request.prompt_version,
            "system": request.system,
            "user": request.user,
            "document_hash": hashlib.sha256(request.source.encode()).hexdigest(),
            "schema": request.schema.model_json_schema(),
            "max_output_tokens": request.max_output_tokens,
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()

    def get(self, key: str) -> str | None:
        if not self.enabled:
            return None
        try:
            return (self.directory / f"{key}.json").read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None

    def put(self, key: str, value: str) -> None:
        if not self.enabled:
            return
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(value)
            os.replace(name, self.directory / f"{key}.json")
        finally:
            if os.path.exists(name):
                os.unlink(name)
