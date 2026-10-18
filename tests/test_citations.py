"""Tests for the citation and finding validator."""
from __future__ import annotations

import pytest

from backend.app.models.schemas import (
    AgentRequest,
    AgentResponse,
    Citation,
    EvidencePassage,
    Finding,
)
from backend.app.safety.citation_validator import (
    CitationCheck,
    ValidationReport,
    backfill_citation_metadata,
    normalize_text,
    validate_response,
    verify_citation,
)
from tests.fixtures.sample_evidence import (
    ALL_SAMPLE_PASSAGES,
    RENTAL_AMBIGUOUS_PASSAGE,
    RENTAL_SECURITY_DEPOSIT_PASSAGE,
    RENTAL_TERMINATION_PASSAGE,
    make_request,
)


@pytest.fixture
def evidence_by_id() -> dict[str, EvidencePassage]:
    return {p.source_id: p for p in ALL_SAMPLE_PASSAGES}


@pytest.fixture
def standard_request() -> AgentRequest:
    return make_request(
        question="What are the lease termination terms?",
        passages=ALL_SAMPLE_PASSAGES,
        sufficient=True,
    )


def test_normalize_text_whitespace_and_unicode() -> None:
    raw = "  The   tenant’s   repair\nrequests \t must be — addressed  "
    norm = normalize_text(raw)
    assert norm == "The tenant's repair requests must be - addressed"
    # Verify no lowercasing
    assert "The" in norm


def test_exact_quote_passes_and_is_verified(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type=RENTAL_TERMINATION_PASSAGE.source_type,
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    check = verify_citation(cite, evidence_by_id)
    assert check.ok is True
    assert check.reason == "OK"


def test_quote_with_newline_double_space_curly_apostrophe_passes(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    cite = Citation(
        source_id=RENTAL_AMBIGUOUS_PASSAGE.source_id,
        source_type=RENTAL_AMBIGUOUS_PASSAGE.source_type,
        page=RENTAL_AMBIGUOUS_PASSAGE.page,
        section=RENTAL_AMBIGUOUS_PASSAGE.section,
        quote="The tenant's repair requests must be addressed within a reasonable time after landlord receives written notification.",
    )
    check = verify_citation(cite, evidence_by_id)
    assert check.ok is True
    assert check.reason == "OK"


def test_fabricated_quote_fails_quote_not_found(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type=RENTAL_TERMINATION_PASSAGE.source_type,
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote="The landlord must pay a penalty of five thousand dollars upon breach.",
    )
    check = verify_citation(cite, evidence_by_id)
    assert check.ok is False
    assert check.reason == "QUOTE_NOT_FOUND"


def test_quote_from_passage_a_under_source_id_of_passage_b_fails(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    cite = Citation(
        source_id=RENTAL_SECURITY_DEPOSIT_PASSAGE.source_id,
        source_type=RENTAL_SECURITY_DEPOSIT_PASSAGE.source_type,
        page=RENTAL_SECURITY_DEPOSIT_PASSAGE.page,
        section=RENTAL_SECURITY_DEPOSIT_PASSAGE.section,
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    check = verify_citation(cite, evidence_by_id)
    assert check.ok is False
    assert check.reason == "QUOTE_NOT_FOUND"


def test_unknown_source_id_fails(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    cite = Citation(
        source_id="nonexistent-source-id#clause-99",
        source_type="contract",
        quote="Either party may terminate this agreement",
    )
    check = verify_citation(cite, evidence_by_id)
    assert check.ok is False
    assert check.reason == "UNKNOWN_SOURCE_ID"


def test_wrong_page_section_source_type_each_fail(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    base_quote = "Either party may terminate this agreement upon thirty (30) days written notice"

    cite_wrong_page = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        page=99,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote=base_quote,
    )
    assert verify_citation(cite_wrong_page, evidence_by_id) == CitationCheck(
        ok=False, reason="PAGE_MISMATCH"
    )

    cite_wrong_sec = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        page=RENTAL_TERMINATION_PASSAGE.page,
        section="Wrong Section Title",
        quote=base_quote,
    )
    assert verify_citation(cite_wrong_sec, evidence_by_id) == CitationCheck(
        ok=False, reason="SECTION_MISMATCH"
    )

    cite_wrong_type = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="judgment",
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote=base_quote,
    )
    assert verify_citation(cite_wrong_type, evidence_by_id) == CitationCheck(
        ok=False, reason="SOURCE_TYPE_MISMATCH"
    )


def test_too_short_quote_fails(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote="Short",
    )
    check = verify_citation(cite, evidence_by_id)
    assert check.ok is False
    assert check.reason == "QUOTE_TOO_SHORT"


def test_ellipsis_quote_segments(
    evidence_by_id: dict[str, EvidencePassage],
) -> None:
    cite_valid = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote="Either party may terminate...thirty (30) days written notice",
    )
    assert verify_citation(cite_valid, evidence_by_id) == CitationCheck(
        ok=True, reason="OK"
    )

    cite_fake_segment = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote="Either party may terminate...landlord must provide golden carriage",
    )
    assert verify_citation(cite_fake_segment, evidence_by_id) == CitationCheck(
        ok=False, reason="QUOTE_NOT_FOUND"
    )

    cite_reversed_order = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote="thirty (30) days written notice...Either party may terminate",
    )
    assert verify_citation(cite_reversed_order, evidence_by_id) == CitationCheck(
        ok=False, reason="QUOTE_NOT_FOUND"
    )

    cite_short_segment = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        page=RENTAL_TERMINATION_PASSAGE.page,
        section=RENTAL_TERMINATION_PASSAGE.section,
        quote="Either party may terminate...xyz",
    )
    assert verify_citation(cite_short_segment, evidence_by_id) == CitationCheck(
        ok=False, reason="QUOTE_TOO_SHORT"
    )


def test_paraphrased_explicit_text_dropped(
    standard_request: AgentRequest,
) -> None:
    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    finding = Finding(
        title="Termination Notice",
        explicit_text="The tenant or owner can cancel the lease with a 30-day notice period.",
        plain_language_explanation="Notice period explanation.",
        evidence=[cite],
    )
    response = AgentResponse(
        answer="The lease can be terminated with notice.",
        findings=[finding],
        evidence_sufficient=True,
    )
    validated, report = validate_response(response, standard_request)
    assert validated.status == "abstained"
    assert len(validated.findings) == 0
    assert report.dropped_findings == 1
    assert (0, "EXPLICIT_TEXT_NOT_IN_PASSAGE") in report.failures


def test_explicit_text_under_12_chars_is_dropped(
    standard_request: AgentRequest,
) -> None:
    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    finding = Finding(
        title="Short Finding",
        explicit_text="terminate",
        plain_language_explanation="Short text.",
        evidence=[cite],
    )
    response = AgentResponse(
        answer="Termination allowed.",
        findings=[finding],
        evidence_sufficient=True,
    )
    validated, report = validate_response(response, standard_request)
    assert validated.status == "abstained"
    assert len(validated.findings) == 0
    assert (0, "EXPLICIT_TEXT_TOO_SHORT") in report.failures


def test_finding_with_zero_citations_dropped(
    standard_request: AgentRequest,
) -> None:
    finding = Finding(
        title="No Citation Finding",
        explicit_text="Either party may terminate this agreement upon thirty (30) days written notice",
        plain_language_explanation="No citations provided.",
        evidence=[],
    )
    response = AgentResponse(
        answer="Termination rules.",
        findings=[finding],
        evidence_sufficient=True,
    )
    validated, report = validate_response(response, standard_request)
    assert validated.status == "abstained"
    assert len(validated.findings) == 0
    assert (0, "NO_VERIFIED_CITATIONS") in report.failures


def test_all_dropped_abstained_and_professional_review_recommended(
    standard_request: AgentRequest,
) -> None:
    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        quote="This text does not exist anywhere in the agreement.",
    )
    finding = Finding(
        title="Unverifiable Finding",
        explicit_text="This text does not exist anywhere in the agreement.",
        plain_language_explanation="Fabricated text.",
        evidence=[cite],
    )
    response = AgentResponse(
        answer="Model unverified answer.",
        findings=[finding],
        evidence_sufficient=True,
    )
    validated, report = validate_response(response, standard_request)
    assert validated.status == "abstained"
    assert validated.findings == []
    assert validated.evidence_sufficient is False
    assert validated.professional_review_recommended is True
    assert validated.limitation == "No verifiable evidence supported an answer."
    assert "unverified answer" not in validated.answer
    assert report.dropped_findings == 1


def test_mixed_valid_invalid_keeps_only_valid_and_rebuilds_answer(
    standard_request: AgentRequest,
) -> None:
    cite_valid = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    finding_valid = Finding(
        title="Termination Notice",
        explicit_text="Either party may terminate this agreement upon thirty (30) days written notice",
        plain_language_explanation="Valid termination clause.",
        evidence=[cite_valid],
    )

    cite_invalid = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        quote="Fabricated penalty of ten thousand dollars.",
    )
    finding_invalid = Finding(
        title="Fabricated Penalty",
        explicit_text="Fabricated penalty of ten thousand dollars.",
        plain_language_explanation="Invalid penalty.",
        evidence=[cite_invalid],
    )

    response = AgentResponse(
        answer="The lease contains termination rules and a ten thousand dollar penalty.",
        findings=[finding_valid, finding_invalid],
        evidence_sufficient=True,
        status="answered",
    )
    validated, report = validate_response(response, standard_request)
    assert validated.status == "answered"
    assert len(validated.findings) == 1
    assert validated.findings[0].title == "Termination Notice"
    assert validated.findings[0].evidence[0].verified is True
    assert validated.answer == "The document addresses: Termination Notice."
    assert report.kept_findings == 1
    assert report.dropped_findings == 1


def test_refused_response_passes_through_unchanged(
    standard_request: AgentRequest,
) -> None:
    response = AgentResponse(
        answer="I cannot assist with this request.",
        findings=[],
        evidence_sufficient=False,
        limitation="Refused due to ethical guardrails.",
        professional_review_recommended=False,
        status="refused",
    )
    validated, report = validate_response(response, standard_request)
    assert validated == response
    assert report.total_findings == 0
    assert report.dropped_findings == 0


def test_input_not_mutated(
    standard_request: AgentRequest,
) -> None:
    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="legislation",  # intentionally wrong to verify backfill doesn't mutate input
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    finding = Finding(
        title="Termination Notice",
        explicit_text="Either party may terminate this agreement upon thirty (30) days written notice",
        plain_language_explanation="Valid termination.",
        evidence=[cite],
    )
    response = AgentResponse(
        answer="Original answer.",
        findings=[finding],
        evidence_sufficient=True,
    )
    orig_resp_dump = response.model_dump()
    orig_req_dump = standard_request.model_dump()

    validate_response(response, standard_request)

    assert response.model_dump() == orig_resp_dump
    assert standard_request.model_dump() == orig_req_dump


def test_validation_report_repr_contains_no_quote_text(
    standard_request: AgentRequest,
) -> None:
    secret_quote = "SECRET_QUOTE_FOR_TESTING_123456"
    secret_explicit = "SECRET_EXPLICIT_TEXT_123456"

    cite = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="contract",
        quote=secret_quote,
    )
    finding = Finding(
        title="Secret Finding",
        explicit_text=secret_explicit,
        plain_language_explanation="Secret explanation.",
        evidence=[cite],
    )
    response = AgentResponse(
        answer="Answer mentioning secret.",
        findings=[finding],
        evidence_sufficient=True,
    )

    _, report = validate_response(response, standard_request)
    rep_str = repr(report)

    assert secret_quote not in rep_str
    assert secret_explicit not in rep_str
    assert standard_request.question not in rep_str


def test_backfill_fixes_wrong_metadata_leaves_unknown_source_id_failing(
    standard_request: AgentRequest,
) -> None:
    cite_known = Citation(
        source_id=RENTAL_TERMINATION_PASSAGE.source_id,
        source_type="legislation",  # wrong
        page=99,                    # wrong
        section="Wrong Section",    # wrong
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    cite_unknown = Citation(
        source_id="completely-unknown-id",
        source_type="legislation",
        page=42,
        section="Alien Section",
        quote="Either party may terminate this agreement upon thirty (30) days written notice",
    )
    finding = Finding(
        title="Backfill Test",
        explicit_text="Either party may terminate this agreement upon thirty (30) days written notice",
        plain_language_explanation="Testing backfill behavior.",
        evidence=[cite_known, cite_unknown],
    )
    response = AgentResponse(
        answer="Testing backfill.",
        findings=[finding],
        evidence_sufficient=True,
    )

    backfilled = backfill_citation_metadata(response, standard_request)

    # Known citation was backfilled
    c_known = backfilled.findings[0].evidence[0]
    assert c_known.source_type == RENTAL_TERMINATION_PASSAGE.source_type
    assert c_known.page == RENTAL_TERMINATION_PASSAGE.page
    assert c_known.section == RENTAL_TERMINATION_PASSAGE.section

    # Unknown citation was left untouched
    c_unknown = backfilled.findings[0].evidence[1]
    assert c_unknown.source_id == "completely-unknown-id"
    assert c_unknown.page == 42
    assert c_unknown.section == "Alien Section"
