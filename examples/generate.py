"""Generate original, freely redistributable PDF and exact-size text examples on CPU."""

from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject


def text_pdf(pages: list[str]) -> bytes:
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        operations = ["BT /F1 11 Tf 40 790 Td 14 TL"]
        for line in text.splitlines():
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            operations.append(f"({escaped}) Tj T*")
        operations.append("ET")
        stream = StreamObject()
        stream.set_data("\n".join(operations).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def long_document(size: int) -> str:
    head = "Job Description\nPosition: Workflow Engineer\n"
    tail = "\nSkills: TailEvidence\nSummary: All chunks are processed.\n"
    filler = "Background context for a fictional document.\n"
    remaining = size - len(head) - len(tail)
    return head + (filler * (remaining // len(filler) + 1))[:remaining] + tail


def main() -> None:
    root = Path(__file__).parent
    for size in (1000, 10_000, 50_000):
        (root / f"long_{size}.txt").write_text(long_document(size), encoding="utf-8")
    (root / "sample.pdf").write_bytes(
        text_pdf(
            [
                "Technical Report\nTitle: Text PDF pipeline\nSystem: Local CPU workflow",
                "Limitations: OCR is not supported\nSummary: Page evidence is retained.",
            ]
        )
    )


if __name__ == "__main__":
    main()
