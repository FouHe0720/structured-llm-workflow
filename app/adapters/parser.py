"""UTF-8 parser with stable Unicode character offsets."""

import hashlib
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.domain.errors import WorkflowError
from app.domain.models import Document, Segment


class Parser:
    def __init__(
        self, max_bytes: int = 2_097_152, max_chars: int = 200_000, max_pages: int = 50
    ) -> None:
        self.max_bytes = max_bytes
        self.max_chars = max_chars
        self.max_pages = max_pages

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
        if Path(name).suffix.lower() == ".pdf":
            return self._pdf(data, Path(name).name)
        if Path(name).suffix.lower() not in {".txt", ".md"}:
            raise WorkflowError("unsupported_type", "Supported extensions: .txt, .md, .pdf")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise WorkflowError("invalid_encoding", "Text must be UTF-8") from exc
        return self.parse_text(text, Path(name).name)

    def _pdf(self, data: bytes, name: str) -> Document:
        try:
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise WorkflowError("encrypted_pdf", "Encrypted PDF is unsupported")
            if len(reader.pages) > self.max_pages:
                raise WorkflowError("too_many_pages", "PDF exceeds page limit")
            pages = []
            total = 0
            for page in reader.pages:
                content = page.get_contents()
                if content and len(content.get_data()) > 8_388_608:
                    raise WorkflowError("pdf_stream_too_large", "Decoded PDF page exceeds 8 MiB")
                text = page.extract_text() or ""
                total += len(text)
                if total > self.max_chars:
                    raise WorkflowError("file_too_large", "PDF exceeds extracted character limit")
                pages.append(text)
        except WorkflowError:
            raise
        except Exception as exc:
            raise WorkflowError("pdf_parse_error", "Cannot parse this PDF") from exc
        if not any(text.strip() for text in pages):
            raise WorkflowError(
                "ocr_not_supported", "PDF has no extractable text; OCR is unsupported"
            )
        document = self.parse_text("\n\f\n".join(pages), name)
        document.pages = len(pages)
        document.segments = []
        offset = 0
        for page_number, text in enumerate(pages, 1):
            if not text.strip():
                document.warnings.append(f"Page {page_number} has no text; OCR is unsupported.")
            for match in re.finditer(r"[^\n]+", text):
                if match.group().strip():
                    document.segments.append(
                        Segment(
                            paragraph=len(document.segments) + 1,
                            page=page_number,
                            start=offset + match.start(),
                            end=offset + match.end(),
                            text=match.group(),
                        )
                    )
            offset += len(text) + 3
        return document

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
