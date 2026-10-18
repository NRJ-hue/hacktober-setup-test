"""Tests for question classification, legal verdict refusal, and response guardrails."""
from __future__ import annotations

import pytest

from backend.app.models.schemas import (
    AgentRequest,
    AgentResponse,
    Citation,
    Finding,
)
from backend.app.safety.response_guard import (
    GuardReport,
    QuestionIntent,
    classify_question,
    enforce_guard,
)
from tests.fixtures.sample_evidence import (
    ALL_SAMPLE_PASSAGES,
    JUDGMENT_PASSAGE,
    LEGISLATION_PASSAGE,
    RENTAL_TERMINATION_PASSAGE,
    make_request,
)


@pytest.fixture
def standard_request() -> AgentRequest:
    return make_request(
        question="What is the notice period in this lease?",
        passages=ALL_SAMPLE_PASSAGES,
        sufficient=True,
    )


@pytest.mark.parametrize(
    "verdict_phrase",
    [
        "Is this enforceable?",
        "Is this legal?",
        "Is this valid?",
        "Is this binding?",
        "Is this illegal?",
        "Is this fair?",
        "Will I win?",
        "Can they sue me?",
        "Should I sign?",
        "Can they do this legally?",
    ],
)
def test_every_verdict_phrasing_refused(
    verdict_phrase: str,
    standard_request: AgentRequest,
) -> None:
    intent = classify_question(verdict_phrase)
    assert intent.kind == "legal_verdict"

    response = AgentResponse(
        answer="Yes, the clause is completely enforceable and legal.",
        findings=[],
        evidence_sufficient=True,
        status="answered",
    )

    guarded, report = enforce_guard(response, standard_request, intent)
    assert guarded.status == "refused"
    assert report.verdict_refused is True
    assert guarded.professional_review_recommended is True
    assert "lawyer" in guarded.limitation.lower()
    assert "verdict" in guarded.answer.lower() or "cannot" in guarded.answer.lower()


def test_outside_document_classification() -> None:
    intent1 = classify_question("What is the law on evictions in my state?")
    assert intent1.kind == "outside_document"

    intent2 = classify_question("What does the law say about security deposits?")
    assert intent2.kind == "outside_document"

    # Mentions document -> normal
    intent3 = classify_question("What is the law on evictions in this lease?")
    assert intent3.kind == "normal"


def test_normal_question_classification() -> None:
    intent1 = classify_question("What is the security deposit amount under clause 5?")
    assert intent1.kind == "normal"

    intent2 = classify_question("When is rent due under this agreement?")
    assert intent2.kind == "normal"


def test_overconfident_answer_rewritten(
    standard_request: AgentRequest,
) -> None:
    finding = Finding(
        title="Payment Term",
        explicit_text="Rent is due on the 1st of each month.",
        plain_language_explanation="This clause is legally binding and you must pay rent on time.",
    )
    response = AgentResponse(
        answer="This agreement is legally binding and you must pay rent on the first. Payment is guaranteed.",
        findings=[finding],
        evidence_sufficient=True,
        status="answered",
    )
    guarded, report = enforce_guard(
        response, standard_request, QuestionIntent(kind="normal")
    )
    assert "is legally binding" not in guarded.answer
    assert "may be legally binding" in guarded.answer
    assert "the document states that you must" in guarded.answer
    assert "is legally binding" not in guarded.findings[0].plain_language_explanation
    assert "may be legally binding" in guarded.findings[0].plain_language_explanation
    assert guarded.professional_review_recommended is True
    assert report.hedged_language_count >= 2


def test_jurisdiction_note_and_escalation_rules(
    standard_request: AgentRequest,
) -> None:
    # 1. Penalty -> jurisdiction note + escalation
    f_penalty = Finding(
        title="Late Fee Penalty",
        category="penalty",
        explicit_text="A late fee penalty of $50 will be charged.",
        plain_language_explanation="Penalty charge.",
        escalation_required=False,
    )
    # 2. Security Deposit -> jurisdiction note + escalation
    f_deposit = Finding(
        title="Security Deposit",
        explicit_text="A security deposit of $1,000 is required.",
        plain_language_explanation="Deposit terms.",
        escalation_required=False,
    )
    # 3. Notice Period -> jurisdiction note, but NO escalation
    f_notice = Finding(
        title="Notice Period",
        explicit_text="Tenant must provide thirty (30) days notice.",
        plain_language_explanation="Notice period requirements.",
        escalation_required=False,
    )

    response = AgentResponse(
        answer="Summary terms.",
        findings=[f_penalty, f_deposit, f_notice],
        evidence_sufficient=True,
    )
    guarded, report = enforce_guard(
        response, standard_request, QuestionIntent(kind="normal")
    )

    # Check uncertainties
    assert "jurisdiction" in guarded.findings[0].uncertainty.lower()
    assert "jurisdiction" in guarded.findings[1].uncertainty.lower()
    assert "jurisdiction" in guarded.findings[2].uncertainty.lower()

    # Check escalations
    assert guarded.findings[0].escalation_required is True
    assert guarded.findings[1].escalation_required is True
    assert guarded.findings[2].escalation_required is False


def test_ambiguity_note_added(
    standard_request: AgentRequest,
) -> None:
    f_ambiguous = Finding(
        title="Repairs Schedule",
        explicit_text="Repairs shall be completed within a reasonable time after notice.",
        plain_language_explanation="Repair timeframe.",
    )
    response = AgentResponse(
        answer="Repair rules.",
        findings=[f_ambiguous],
        evidence_sufficient=True,
    )
    guarded, report = enforce_guard(
        response, standard_request, QuestionIntent(kind="normal")
    )
    assert "ambiguous" in guarded.findings[0].uncertainty.lower()
    assert report.ambiguity_uncertainty_count >= 1


def test_insufficient_evidence_abstains() -> None:
    req = make_request("What is the pet policy?", passages=[], sufficient=False)
    response = AgentResponse(
        answer="Pets are allowed.",
        findings=[],
        evidence_sufficient=False,
        status="answered",
    )
    guarded, report = enforce_guard(
        response, req, QuestionIntent(kind="normal")
    )
    assert guarded.status == "abstained"
    assert guarded.limitation == "The document does not appear to address this."
    assert guarded.evidence_sufficient is False
    assert guarded.professional_review_recommended is True
    assert report.abstentions_count == 1


def test_source_type_separation_prefix(
    standard_request: AgentRequest,
) -> None:
    cite_leg = Citation(
        source_id=LEGISLATION_PASSAGE.source_id,
        source_type="legislation",
        quote="A landlord shall not demand or retain a security deposit",
    )
    f_leg = Finding(
        title="Statutory Deposit Limit",
        explicit_text="A landlord shall not demand or retain a security deposit",
        plain_language_explanation="Limit on deposit amount.",
        interpretation_or_concern="Applies across Ontario.",
        evidence=[cite_leg],
    )

    cite_judg = Citation(
        source_id=JUDGMENT_PASSAGE.source_id,
        source_type="judgment",
        quote="Held, that forty-eight hours did not constitute a 'reasonable time'",
    )
    f_judg = Finding(
        title="Reasonable Time Precedent",
        explicit_text="Held, that forty-eight hours did not constitute a 'reasonable time'",
        plain_language_explanation="Precedent ruling.",
        interpretation_or_concern="Court decision on repair timeframes.",
        evidence=[cite_judg],
    )

    response = AgentResponse(
        answer="External sources overview.",
        findings=[f_leg, f_judg],
        evidence_sufficient=True,
    )
    guarded, report = enforce_guard(
        response, standard_request, QuestionIntent(kind="normal")
    )

    assert guarded.findings[0].interpretation_or_concern.startswith(
        "This comes from legislation, not a term of the contract."
    )
    assert guarded.findings[1].interpretation_or_concern.startswith(
        "This comes from a court judgment, not a term of the contract."
    )
    assert report.source_separation_count == 2


def test_input_not_mutated(
    standard_request: AgentRequest,
) -> None:
    finding = Finding(
        title="Late Fee Penalty",
        explicit_text="A penalty of $50 applies.",
        plain_language_explanation="Penalty.",
        escalation_required=False,
    )
    response = AgentResponse(
        answer="This is legally binding and you must pay.",
        findings=[finding],
        evidence_sufficient=True,
    )
    orig_resp_dump = response.model_dump()
    orig_req_dump = standard_request.model_dump()

    enforce_guard(response, standard_request, QuestionIntent(kind="normal"))

    assert response.model_dump() == orig_resp_dump
    assert standard_request.model_dump() == orig_req_dump


def test_guard_report_repr_has_no_text(
    standard_request: AgentRequest,
) -> None:
    finding = Finding(
        title="Secret Finding Title 12345",
        explicit_text="Secret document text 67890",
        plain_language_explanation="Secret explanation text.",
    )
    response = AgentResponse(
        answer="Secret answer text 99999",
        findings=[finding],
        evidence_sufficient=True,
    )
    _, report = enforce_guard(
        response, standard_request, QuestionIntent(kind="legal_verdict")
    )
    rep_str = repr(report)

    assert "Secret Finding Title" not in rep_str
    assert "Secret document text" not in rep_str
    assert "Secret explanation" not in rep_str
    assert "Secret answer" not in rep_str
    assert standard_request.question not in rep_str
