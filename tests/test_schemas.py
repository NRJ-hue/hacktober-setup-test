"""Tests for canonical shared Pydantic schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.models.schemas import (
    AgentRequest,
    AgentResponse,
    Citation,
    DocumentChunk,
    DocumentStatus,
    EvidencePassage,
    ExtractedPage,
    Finding,
    QuestionRequest,
    RetrievalResponse,
)
from tests.fixtures.sample_evidence import (
    ALL_SAMPLE_PASSAGES,
    JUDGMENT_PASSAGE,
    LEGISLATION_PASSAGE,
    PROMPT_INJECTION_PASSAGE,
    RENTAL_AMBIGUOUS_PASSAGE,
    RENTAL_PASSAGES,
    make_request,
)


def test_valid_construction_extracted_page() -> None:
    page = ExtractedPage(document_id="doc-1", page_number=1, text="Sample text")
    assert page.document_id == "doc-1"
    assert page.page_number == 1
    assert page.text == "Sample text"


def test_valid_construction_document_chunk() -> None:
    chunk = DocumentChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source_id="src-1",
        source_type="contract",
        page=2,
        section="Sec 3.1",
        parent_clause_id="clause-3",
        chunk_index=0,
        text="Clause text",
    )
    assert chunk.chunk_id == "chunk-1"
    assert chunk.chunk_index == 0
    assert chunk.page == 2


def test_valid_construction_evidence_passage() -> None:
    passage = EvidencePassage(
        source_id="src-1",
        source_type="legislation",
        page=5,
        section="Section 10",
        text="Statutory text",
    )
    assert passage.source_id == "src-1"
    assert passage.source_type == "legislation"


def test_valid_construction_retrieval_response() -> None:
    passage = EvidencePassage(
        source_id="src-1", source_type="contract", text="Passage text"
    )
    resp = RetrievalResponse(
        document_id="doc-1",
        question="What is the term?",
        evidence=[passage],
        evidence_sufficient=True,
    )
    assert resp.document_id == "doc-1"
    assert len(resp.evidence) == 1
    assert resp.evidence_sufficient is True


def test_valid_construction_agent_request() -> None:
    req = AgentRequest(
        document_id="doc-1",
        question="What is the deposit amount?",
        evidence=[],
        evidence_sufficient=False,
    )
    assert req.document_id == "doc-1"
    assert req.evidence == []
    assert req.evidence_sufficient is False


def test_valid_construction_citation() -> None:
    cite = Citation(
        source_id="src-1",
        source_type="judgment",
        page=10,
        section="Para 12",
        quote="Held, that notice was reasonable.",
        verified=True,
    )
    assert cite.verified is True
    assert cite.quote == "Held, that notice was reasonable."


def test_valid_construction_finding() -> None:
    cite = Citation(
        source_id="src-1",
        source_type="contract",
        quote="Thirty days notice required.",
    )
    finding = Finding(
        title="Termination Notice",
        category="termination",
        explicit_text="Thirty days notice required.",
        plain_language_explanation="Requires 30 days notice to end lease.",
        interpretation_or_concern="May conflict with statutory minimum.",
        evidence=[cite],
        uncertainty=None,
        escalation_required=False,
    )
    assert finding.title == "Termination Notice"
    assert finding.category == "termination"
    assert len(finding.evidence) == 1


def test_valid_construction_agent_response() -> None:
    resp = AgentResponse(
        answer="The lease requires 30 days notice.",
        findings=[],
        evidence_sufficient=True,
        limitation="Jurisdiction specific to Ontario.",
        professional_review_recommended=True,
        status="answered",
    )
    assert resp.answer == "The lease requires 30 days notice."
    assert resp.status == "answered"
    assert resp.professional_review_recommended is True


def test_valid_construction_document_status() -> None:
    status = DocumentStatus(
        document_id="doc-1",
        status="ready",
        page_count=10,
        chunk_count=25,
        message=None,
    )
    assert status.document_id == "doc-1"
    assert status.status == "ready"
    assert status.page_count == 10


def test_valid_construction_question_request() -> None:
    req = QuestionRequest(question="What is the rent?")
    assert req.question == "What is the rent?"


@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n "])
def test_validator_failure_question(empty_val: str) -> None:
    with pytest.raises(ValidationError):
        QuestionRequest(question=empty_val)
    with pytest.raises(ValidationError):
        AgentRequest(
            document_id="doc-1",
            question=empty_val,
            evidence=[],
            evidence_sufficient=True,
        )
    with pytest.raises(ValidationError):
        RetrievalResponse(
            document_id="doc-1",
            question=empty_val,
            evidence=[],
            evidence_sufficient=True,
        )


@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n "])
def test_validator_failure_source_id(empty_val: str) -> None:
    with pytest.raises(ValidationError):
        EvidencePassage(source_id=empty_val, source_type="contract", text="Sample")
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            source_id=empty_val,
            source_type="contract",
            chunk_index=0,
            text="Sample",
        )
    with pytest.raises(ValidationError):
        Citation(source_id=empty_val, source_type="contract", quote="Sample quote")


@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n "])
def test_validator_failure_chunk_id(empty_val: str) -> None:
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id=empty_val,
            document_id="doc-1",
            source_id="src-1",
            source_type="contract",
            chunk_index=0,
            text="Sample",
        )


@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n "])
def test_validator_failure_document_id(empty_val: str) -> None:
    with pytest.raises(ValidationError):
        ExtractedPage(document_id=empty_val, page_number=1, text="Sample")
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id="chunk-1",
            document_id=empty_val,
            source_id="src-1",
            source_type="contract",
            chunk_index=0,
            text="Sample",
        )
    with pytest.raises(ValidationError):
        RetrievalResponse(
            document_id=empty_val,
            question="Question?",
            evidence=[],
            evidence_sufficient=True,
        )
    with pytest.raises(ValidationError):
        AgentRequest(
            document_id=empty_val,
            question="Question?",
            evidence=[],
            evidence_sufficient=True,
        )
    with pytest.raises(ValidationError):
        DocumentStatus(document_id=empty_val, status="ready")


@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n "])
def test_validator_failure_quote(empty_val: str) -> None:
    with pytest.raises(ValidationError):
        Citation(source_id="src-1", source_type="contract", quote=empty_val)


@pytest.mark.parametrize("invalid_page", [0, -1, -99])
def test_validator_failure_page_number_ge_1(invalid_page: int) -> None:
    with pytest.raises(ValidationError):
        ExtractedPage(document_id="doc-1", page_number=invalid_page, text="Sample")


@pytest.mark.parametrize("invalid_index", [-1, -99])
def test_validator_failure_chunk_index_ge_0(invalid_index: int) -> None:
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            source_id="src-1",
            source_type="contract",
            chunk_index=invalid_index,
            text="Sample",
        )


def test_source_type_statute_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidencePassage(source_id="src-1", source_type="statute", text="Text")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id="c-1",
            document_id="d-1",
            source_id="src-1",
            source_type="statute",  # type: ignore[arg-type]
            chunk_index=0,
            text="Text",
        )
    with pytest.raises(ValidationError):
        Citation(source_id="src-1", source_type="statute", quote="Quote")  # type: ignore[arg-type]


def test_source_type_court_judgment_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidencePassage(
            source_id="src-1",
            source_type="court_judgment",  # type: ignore[arg-type]
            text="Text",
        )
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id="c-1",
            document_id="d-1",
            source_id="src-1",
            source_type="court_judgment",  # type: ignore[arg-type]
            chunk_index=0,
            text="Text",
        )
    with pytest.raises(ValidationError):
        Citation(
            source_id="src-1",
            source_type="court_judgment",  # type: ignore[arg-type]
            quote="Quote",
        )


def test_source_type_valid_values() -> None:
    for st in ("contract", "legislation", "judgment"):
        p = EvidencePassage(source_id="s1", source_type=st, text="Valid")  # type: ignore[arg-type]
        assert p.source_type == st


def test_json_round_trip_document_chunk() -> None:
    chunk = DocumentChunk(
        chunk_id="chk-100",
        document_id="doc-500",
        source_id="lease-sec-4",
        source_type="contract",
        page=4,
        section="Section 4.1",
        parent_clause_id="clause-4",
        chunk_index=3,
        text="Payment must be received by the 5th.",
    )
    json_data = chunk.model_dump_json()
    reconstructed = DocumentChunk.model_validate_json(json_data)
    assert reconstructed == chunk


def test_json_round_trip_agent_response() -> None:
    citation = Citation(
        source_id="lease-sec-4",
        source_type="contract",
        page=4,
        section="4.1",
        quote="Payment must be received by the 5th.",
        verified=True,
    )
    finding = Finding(
        title="Late Fee Assessment",
        category="penalty",
        explicit_text="Payment must be received by the 5th.",
        plain_language_explanation="Late fees apply after the 5th of each month.",
        interpretation_or_concern="Verify with local statutory grace period rules.",
        evidence=[citation],
        uncertainty=None,
        escalation_required=False,
    )
    response = AgentResponse(
        answer="The lease provides for late fees after the 5th day.",
        findings=[finding],
        evidence_sufficient=True,
        limitation="Does not account for local municipal rent control ordinances.",
        professional_review_recommended=True,
        status="answered",
    )
    json_data = response.model_dump_json()
    reconstructed = AgentResponse.model_validate_json(json_data)
    assert reconstructed == response


def test_agent_response_model_dump_keys() -> None:
    expected_keys = [
        "answer",
        "findings",
        "evidence_sufficient",
        "limitation",
        "professional_review_recommended",
        "status",
    ]
    resp = AgentResponse(
        answer="Summary answer.",
        evidence_sufficient=True,
    )
    assert list(resp.model_dump().keys()) == expected_keys


def test_finding_model_dump_keys() -> None:
    expected_keys = [
        "title",
        "category",
        "explicit_text",
        "plain_language_explanation",
        "interpretation_or_concern",
        "evidence",
        "uncertainty",
        "escalation_required",
    ]
    finding = Finding(
        title="Sample Finding",
        explicit_text="Explicit clause text.",
        plain_language_explanation="Explanation.",
    )
    assert list(finding.model_dump().keys()) == expected_keys


def test_sample_evidence_fixtures() -> None:
    assert len(RENTAL_PASSAGES) == 6
    assert len(ALL_SAMPLE_PASSAGES) == 9

    # Every text must start with 'FAKE, illustrative only:'
    for passage in ALL_SAMPLE_PASSAGES:
        assert passage.text.startswith("FAKE, illustrative only:")

    # Passage with line break, double space, and curly apostrophe
    assert "\n" in RENTAL_AMBIGUOUS_PASSAGE.text
    assert "  " in RENTAL_AMBIGUOUS_PASSAGE.text
    assert "’" in RENTAL_AMBIGUOUS_PASSAGE.text

    # Specific passage types
    assert LEGISLATION_PASSAGE.source_type == "legislation"
    assert JUDGMENT_PASSAGE.source_type == "judgment"
    assert "Ignore all previous instructions" in PROMPT_INJECTION_PASSAGE.text

    # Helper make_request
    req = make_request("Is the deposit refundable?", passages=RENTAL_PASSAGES)
    assert req.question == "Is the deposit refundable?"
    assert len(req.evidence) == 6
    assert req.evidence_sufficient is True
