"""Canonical shared Pydantic schemas for the legal document triage agent."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, ValidationInfo, field_validator

SourceType = Literal["contract", "legislation", "judgment"]

FindingCategory = Literal[
    "obligation",
    "right",
    "deadline",
    "penalty",
    "termination",
    "ambiguity",
    "missing_information",
    "potential_legal_concern",
    "other",
]

AgentResponseStatus = Literal["answered", "abstained", "refused", "error"]

DocumentProcessingStatus = Literal["processing", "ready", "failed", "deleted"]


def _validate_non_empty_str(v: str, field_name: str) -> str:
    """Validate that a string value is non-empty after stripping whitespace."""
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{field_name} must be non-empty after strip")
    return v


class ExtractedPage(BaseModel):
    """Raw extracted text from a single document page."""

    document_id: str
    page_number: int = Field(ge=1)
    text: str

    @field_validator("document_id")
    @classmethod
    def _check_document_id(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "document_id")


class DocumentChunk(BaseModel):
    """Indexed chunk of a legal document with source metadata."""

    chunk_id: str
    document_id: str
    source_id: str
    source_type: SourceType
    page: int | None = None
    section: str | None = None
    parent_clause_id: str | None = None
    chunk_index: int = Field(ge=0)
    text: str

    @field_validator("chunk_id", "document_id", "source_id")
    @classmethod
    def _check_ids(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "id")


class EvidencePassage(BaseModel):
    """Retrieved evidence passage supplied to the triage agent."""

    source_id: str
    source_type: SourceType
    page: int | None = None
    section: str | None = None
    text: str

    @field_validator("source_id")
    @classmethod
    def _check_source_id(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "source_id")


class RetrievalResponse(BaseModel):
    """Retrieved evidence passages and sufficiency assessment for a question."""

    document_id: str
    question: str
    evidence: list[EvidencePassage] = Field(default_factory=list)
    evidence_sufficient: bool

    @field_validator("document_id", "question")
    @classmethod
    def _check_non_empty(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "field")


class AgentRequest(BaseModel):
    """Request payload sent to the legal triage agent."""

    document_id: str
    question: str
    evidence: list[EvidencePassage] = Field(default_factory=list)
    evidence_sufficient: bool

    @field_validator("document_id", "question")
    @classmethod
    def _check_non_empty(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "field")


class Citation(BaseModel):
    """Verifiable citation linking a finding to an evidence passage."""

    source_id: str
    source_type: SourceType
    page: int | None = None
    section: str | None = None
    quote: str
    verified: bool = False

    @field_validator("source_id", "quote")
    @classmethod
    def _check_non_empty(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "field")


class Finding(BaseModel):
    """Specific legal finding extracted from analyzed evidence."""

    title: str
    category: FindingCategory = "other"
    explicit_text: str
    plain_language_explanation: str
    interpretation_or_concern: str | None = None
    evidence: list[Citation] = Field(default_factory=list)
    uncertainty: str | None = None
    escalation_required: bool = False


class AgentResponse(BaseModel):
    """Structured response returned by the legal triage agent."""

    answer: str
    findings: list[Finding] = Field(default_factory=list)
    evidence_sufficient: bool
    limitation: str | None = None
    professional_review_recommended: bool = False
    status: AgentResponseStatus = "answered"


class DocumentStatus(BaseModel):
    """Current ingestion and processing status of a document."""

    document_id: str
    status: DocumentProcessingStatus
    page_count: int | None = None
    chunk_count: int | None = None
    message: str | None = None

    @field_validator("document_id")
    @classmethod
    def _check_document_id(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "document_id")


class QuestionRequest(BaseModel):
    """API request payload for asking a question about a document."""

    question: str

    @field_validator("question")
    @classmethod
    def _check_question(cls, v: str, info: ValidationInfo) -> str:
        return _validate_non_empty_str(v, info.field_name or "question")
