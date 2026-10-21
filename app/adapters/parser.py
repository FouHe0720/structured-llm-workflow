"""UTF-8 parser with stable Unicode character offsets."""

import hashlib
import re
from pathlib import Path

from app.domain.errors import WorkflowError
from app.domain.models import Document, Segment


class Parser:
    def __init__(self, max_bytes: int = 2_097_152, max_chars: int = 200_000) -> None:
        self.max_bytes = max_bytes
        self.max_chars = max_chars

    def parse_file(self, path: Path) -> Document:
        try:
            if path.stat().st_size > self.max_bytes:
                raise WorkflowError("file_too_large", "File exceeds byte limit")
            return self.parse_bytes(path.read_bytes(), path.name)
        except OSError as exc:
            raise WorkflowError("file_read_error", "Cannot read input file") from exc

    def parse_bytes(self, data: bytes, name: str = "input.txt") -> Document:
        if len(data) > self.max_bytes:
            raise WorkflowError("file_too_large", "File exceeds byte limit")
        if Path(name).suffix.lower() not in {".txt", ".md"}:
            raise WorkflowError("unsupported_type", "Supported extensions: .txt, .md")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise WorkflowError("invalid_encoding", "Text must be UTF-8") from exc
        return self.parse_text(text, Path(name).name)

    def parse_text(self, text: str, name: str = "input.txt") -> Document:
        if len(text.encode("utf-8")) > self.max_bytes or len(text) > self.max_chars:
            raise WorkflowError("file_too_large", "Text exceeds byte or character limit")
        if not text.strip() or "\x00" in text:
            raise WorkflowError("empty_or_binary", "Expected nonempty text without NUL bytes")
        segments = [
            Segment(paragraph=i, page=None, start=m.start(), end=m.end(), text=m.group())
            for i, m in enumerate(re.finditer(r"[^\n]+", text), 1)
            if m.group().strip()
        ]
        return Document(
            name=Path(name).name,
            text=text,
            sha256=hashlib.sha256(text.encode()).hexdigest(),
            pages=0,
            segments=segments,
        )
