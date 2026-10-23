"""Shared contracts. Missing source facts must remain null or empty lists."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DocumentType(str, Enum):
    JOB = "job_description"
    PAPER = "paper_abstract"
    MEETING = "meeting_minutes"
    REPORT = "technical_report"
    CAMPUS = "campus_admission"
    UNKNOWN = "unknown"


class JobInfo(StrictModel):
    position: str | None
    skills: list[str]
    experience: str | None
    responsibilities: list[str]
    summary: str | None


class PaperInfo(StrictModel):
    title: str | None
    authors: list[str]
    objective: str | None
    method: str | None
    findings: list[str]
    summary: str | None


class MeetingInfo(StrictModel):
    title: str | None
    date: str | None
    participants: list[str]
    decisions: list[str]
    action_items: list[str]
    summary: str | None


class TechnicalReportInfo(StrictModel):
    title: str | None
    system: str | None
    metrics: list[str]
    limitations: list[str]
    recommendations: list[str]
    summary: str | None


class CampusAdmissionInfo(StrictModel):
    title: str | None
    audience: str | None
    registration_window: str | None
    quota_rules: list[str]
    selection_rules: list[str]
    restrictions: list[str]
    summary: str | None


class UnknownInfo(StrictModel):
    summary: str | None


Extraction = (
    JobInfo | PaperInfo | MeetingInfo | TechnicalReportInfo | CampusAdmissionInfo | UnknownInfo
)


class Classification(StrictModel):
    type: DocumentType


class Highlights(StrictModel):
    highlights: list[str]
    risks: list[str]


class Summary(StrictModel):
    sentences: list[str]


class Segment(StrictModel):
    paragraph: int
    page: int | None
    start: int
    end: int
    text: str


class Document(StrictModel):
    name: str
    text: str
    sha256: str
    pages: int
    segments: list[Segment]
    warnings: list[str] = Field(default_factory=list)


class Evidence(StrictModel):
    field: str
    quote: str
    page: int | None
    paragraph: int
    start: int
    end: int


class Conflict(StrictModel):
    field: Literal[
        "position",
        "experience",
        "title",
        "objective",
        "method",
        "date",
        "system",
        "summary",
        "audience",
        "registration_window",
    ]
    values: list[str]


class AnalysisInsights(StrictModel):
    highlights: list[str]
    risks: list[str]
    conflicts: list[Conflict]


class CallRecord(StrictModel):
    step: str
    model: str
    elapsed_ms: float
    input_tokens: int
    output_tokens: int
    token_source: Literal["provider", "estimated", "cache"]
    success: bool
    cache_hit: bool = False
    error_code: str | None = None
    cost_usd: float | None = None


class Usage(StrictModel):
    calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    token_source: str
    cost_usd: float | None
    validation_success_rate: float
    p50_ms: float
    p95_ms: float
    records: list[CallRecord]


class Metadata(StrictModel):
    name: str
    sha256: str
    characters: int
    pages: int
    chunks: int


class AnalysisReport(StrictModel):
    type: DocumentType
    metadata: Metadata
    extracted: Extraction
    summary: str
    risks_or_highlights: Highlights
    evidence: list[Evidence]
    conflicts: list[Conflict]
    model_info: dict[str, str]
    timings: dict[str, float]
    usage: Usage
    validation_status: Literal["passed"]
    warnings: list[str]

    @model_validator(mode="after")
    def matching_extraction(self) -> "AnalysisReport":
        from schema.model_registry import MODEL_REGISTRY

        if type(self.extracted) is not MODEL_REGISTRY[self.type]:
            raise ValueError("Extraction model does not match document type")
        return self
