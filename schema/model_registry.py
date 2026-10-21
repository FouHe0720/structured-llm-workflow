"""The authoritative document-type → Pydantic/JSON Schema registry."""

from app.domain.models import (
    DocumentType,
    JobInfo,
    MeetingInfo,
    PaperInfo,
    TechnicalReportInfo,
    UnknownInfo,
)

MODEL_REGISTRY = {
    DocumentType.JOB: JobInfo,
    DocumentType.PAPER: PaperInfo,
    DocumentType.MEETING: MeetingInfo,
    DocumentType.REPORT: TechnicalReportInfo,
    DocumentType.UNKNOWN: UnknownInfo,
}


def json_schema(document_type: DocumentType) -> dict:
    return MODEL_REGISTRY[document_type].model_json_schema()
