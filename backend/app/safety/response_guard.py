"""Response guardrails, question classifier, and injection detector for the legal document triage agent."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, NamedTuple

from backend.app.models.schemas import AgentRequest, AgentResponse, Finding


class QuestionIntent(NamedTuple):
    """Classified intent of a user question."""

    kind: Literal["legal_verdict", "outside_document", "normal"]


class InjectionReport(NamedTuple):
    """Result of scanning text for prompt injection patterns."""

    flagged: bool
    pattern_ids: list[str]


@dataclass
class GuardReport:
    """Summary of response guard actions without logging document text, quotes, or questions."""

    intent_kind: str
    actions: list[str] = field(default_factory=list)
    injection_flagged: bool = False
    verdict_refused: bool = False
    hedged_language_count: int = 0
    jurisdiction_uncertainty_count: int = 0
    ambiguity_uncertainty_count: int = 0
    source_separation_count: int = 0
    escalations_count: int = 0
    abstentions_count: int = 0


_VERDICT_PATTERNS = [
    re.compile(
        r"\b(?:is|are)\s+(?:this|it|that|these|the)\s+(?:\w+\s+)*(?:legally\s+)?(?:enforceable|legal|valid|binding|illegal|fair)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are)\s+it\s+(?:legal|illegal|fair|valid|binding|enforceable)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:will|can)\s+(?:i|we)\s+win\b", re.IGNORECASE),
    re.compile(r"\bcan\s+(?:\w+\s+)*sue\s+(?:me|us)\b", re.IGNORECASE),
    re.compile(r"\bshould\s+(?:i|we)\s+sign\b", re.IGNORECASE),
    re.compile(
        r"\bcan\s+(?:\w+\s+)*(?:legally\s+do\s+this|do\s+this\s+legally)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcan\s+(?:they|he|she)\s+do\s+this\s+legally\b", re.IGNORECASE),
    re.compile(r"\bsafe\s+to\s+rely\s+on\b", re.IGNORECASE),
    re.compile(r"\bsafe\s+to\s+sign\b", re.IGNORECASE),
    re.compile(r"\b(?:okay|ok)\s+to\s+sign\b", re.IGNORECASE),
    re.compile(r"\bstand\s+up\s+in\s+court\b", re.IGNORECASE),
    re.compile(r"\bhold\s+up\s+in\s+court\b", re.IGNORECASE),
    re.compile(r"\bwill\s+a\s+court\b", re.IGNORECASE),
    re.compile(r"\bis\s+it\s+a\s+good\s+idea\s+to\s+sign\b", re.IGNORECASE),
    re.compile(r"\bam\s+i\s+protected\b", re.IGNORECASE),
    re.compile(r"\bcan\s+(?:they|he|she)\s+do\s+this\s+to\s+(?:me|us)\b", re.IGNORECASE),
]

_DOC_REF_PATTERNS = [
    re.compile(
        r"\b(?:this|the)\s+(?:document|contract|agreement|lease|clause|section|policy|addendum|rider|text)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:herein|hereunder|above|below)\b", re.IGNORECASE),
]

_GENERAL_LAW_PATTERNS = [
    re.compile(r"\bwhat\s+is\s+the\s+law\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+does\s+the\s+law\s+say\b", re.IGNORECASE),
    re.compile(
        r"\b(?:state|federal|local|statutory|general)\s+law\b", re.IGNORECASE
    ),
    re.compile(r"\bin\s+my\s+state\b", re.IGNORECASE),
    re.compile(
        r"\bin\s+(?:california|new\s+york|texas|ontario|florida|illinois|ohio|georgia)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bstatute\b", re.IGNORECASE),
    re.compile(r"\btenants?\s+rights\b", re.IGNORECASE),
    re.compile(r"\bunder\s+the\s+law\b", re.IGNORECASE),
    re.compile(r"\blaw\s+on\s+\w+\b", re.IGNORECASE),
]


def classify_question(question: str) -> QuestionIntent:
    """Classify user question into legal_verdict, outside_document, or normal."""
    q_clean = re.sub(r"[^\w\s]", " ", question)
    q_clean = re.sub(r"\s+", " ", q_clean).strip()

    # 1. Legal verdict check
    for pat in _VERDICT_PATTERNS:
        if pat.search(q_clean):
            return QuestionIntent(kind="legal_verdict")

    # 2. Outside document check
    has_doc_ref = any(pat.search(q_clean) for pat in _DOC_REF_PATTERNS)
    if not has_doc_ref:
        for pat in _GENERAL_LAW_PATTERNS:
            if pat.search(q_clean):
                return QuestionIntent(kind="outside_document")

    # 3. Default: normal
    return QuestionIntent(kind="normal")


_INJECTION_PATTERNS = [
    (
        "IGNORE_INSTRUCTIONS",
        re.compile(
            r"\b(?:ignore|disregard)\s+(?:(?:all|previous|above)\s+)*instructions\b",
            re.IGNORECASE,
        ),
    ),
    ("YOU_ARE_NOW", re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE)),
    ("SYSTEM_PROMPT", re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE)),
    (
        "REVEAL_INSTRUCTIONS",
        re.compile(r"\breveal\s+your\s+instructions\b", re.IGNORECASE),
    ),
    (
        "RESPOND_ONLY_WITH",
        re.compile(r"\brespond\s+only\s+with\b", re.IGNORECASE),
    ),
    ("DO_NOT_MENTION", re.compile(r"\bdo\s+not\s+mention\b", re.IGNORECASE)),
    (
        "DISREGARD_SAFETY",
        re.compile(r"\bdisregard\s+all\s+safety\b", re.IGNORECASE),
    ),
    (
        "NEW_INSTRUCTIONS",
        re.compile(r"\bnew\s+instructions\b", re.IGNORECASE),
    ),
    ("ROLE_MARKER", re.compile(r"(?m)^\s*(?:SYSTEM|ASSISTANT):")),
]


def detect_injection(text: str) -> InjectionReport:
    """Detect prompt injection patterns in text. Returns pattern IDs only, never text."""
    matched_ids: list[str] = []
    for pid, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            matched_ids.append(pid)

    return InjectionReport(flagged=len(matched_ids) > 0, pattern_ids=matched_ids)


_DEFINITIVE_REPLACEMENTS = [
    (
        re.compile(r"\bthis\s+is\s+illegal\b", re.IGNORECASE),
        "this may be non-compliant",
    ),
    (re.compile(r"\bis\s+illegal\b", re.IGNORECASE), "may be illegal"),
    (re.compile(r"\bis\s+void\b", re.IGNORECASE), "may be void"),
    (re.compile(r"\bwill\s+win\b", re.IGNORECASE), "may prevail"),
    (
        re.compile(r"\byou\s+should\s+sign\b", re.IGNORECASE),
        "you may consult an attorney before signing",
    ),
    (
        re.compile(r"\bis\s+enforceable\b", re.IGNORECASE),
        "may be enforceable",
    ),
    (
        re.compile(r"\bis\s+legally\s+binding\b", re.IGNORECASE),
        "may be legally binding",
    ),
    (
        re.compile(r"\byou\s+must\b", re.IGNORECASE),
        "the document states that you must",
    ),
    (re.compile(r"\bguaranteed\b", re.IGNORECASE), "stated"),
]


def _hedge_text(text: str) -> tuple[str, bool]:
    """Hedge definitive language in text. Returns (hedged_text, was_modified)."""
    if not text:
        return text, False
    modified = False
    result = text
    for pattern, replacement in _DEFINITIVE_REPLACEMENTS:
        if pattern.search(result):
            result = pattern.sub(replacement, result)
            modified = True
    return result, modified


_JURISDICTION_KEYWORDS = (
    "notice period",
    "security deposit",
    "penalty",
    "liquidated damages",
    "late fee",
    "non-compete",
    "noncompete",
    "non compete",
    "termination",
    "rent increase",
    "arbitration",
    "eviction",
)

_ESCALATION_KEYWORDS = (
    "penalty",
    "termination",
    "deposit",
    "non-compete",
    "noncompete",
    "non compete",
)

_AMBIGUOUS_KEYWORDS = (
    "reasonable time",
    "as may be decided",
    "sole discretion",
    "from time to time",
    "as applicable",
)


def enforce_guard(
    response: AgentResponse,
    request: AgentRequest,
    intent: QuestionIntent,
    injection_flagged: bool = False,
) -> tuple[AgentResponse, GuardReport]:
    """Apply safety guardrails to an AgentResponse. Deep copy; never mutates; never raises."""
    try:
        resp = response.model_copy(deep=True)
        report = GuardReport(
            intent_kind=intent.kind, injection_flagged=injection_flagged
        )

        # a. Legal verdict intent handling
        if intent.kind == "legal_verdict":
            kept_findings: list[Finding] = []
            for f in resp.findings:
                # Discard findings asserting legal conclusions or concern categories
                if f.category == "potential_legal_concern" or any(
                    pat.search(f.plain_language_explanation)
                    for pat, _ in _DEFINITIVE_REPLACEMENTS
                ):
                    continue
                kept_findings.append(f)

            resp.findings = kept_findings
            if len(resp.findings) == 0:
                resp.status = "refused"
                report.verdict_refused = True
                report.actions.append("LEGAL_VERDICT_REFUSED")
                resp.answer = (
                    "I cannot provide a legal verdict on whether this document "
                    "or term is enforceable, legal, or binding."
                )
            else:
                resp.answer = (
                    "The document states the referenced terms, but I cannot "
                    "provide a legal verdict on their enforceability."
                )

            resp.limitation = (
                "I can't decide enforceability or legal validity. Consider asking "
                "a lawyer licensed in the relevant jurisdiction."
            )
            resp.professional_review_recommended = True

        # e. Insufficient evidence / empty findings on answered check
        elif not request.evidence_sufficient or (
            len(resp.findings) == 0 and resp.status == "answered"
        ):
            resp.status = "abstained"
            resp.limitation = "The document does not appear to address this."
            resp.evidence_sufficient = False
            resp.professional_review_recommended = True
            resp.findings = []
            resp.answer = (
                "The document does not appear to address this question based on "
                "available evidence."
            )
            report.abstentions_count += 1
            report.actions.append("INSUFFICIENT_EVIDENCE_ABSTAINED")

        # b. Definitive language scan and hedge
        hedged_answer, h_ans = _hedge_text(resp.answer)
        if h_ans:
            resp.answer = hedged_answer
            resp.professional_review_recommended = True
            report.hedged_language_count += 1
            report.actions.append("HEDGED_ANSWER")

        for f in resp.findings:
            h_expl, m_expl = _hedge_text(f.plain_language_explanation)
            if m_expl:
                f.plain_language_explanation = h_expl
                resp.professional_review_recommended = True
                report.hedged_language_count += 1

            if f.interpretation_or_concern:
                h_interp, m_interp = _hedge_text(f.interpretation_or_concern)
                if m_interp:
                    f.interpretation_or_concern = h_interp
                    resp.professional_review_recommended = True
                    report.hedged_language_count += 1

        # c. Jurisdiction-sensitive keywords & escalation
        for f in resp.findings:
            search_text = (
                f"{f.title} {f.category} {f.explicit_text} "
                f"{f.plain_language_explanation}"
            ).lower()
            if any(kw in search_text for kw in _JURISDICTION_KEYWORDS):
                jurisdiction_note = (
                    "Statutory rules and enforcement standards vary by jurisdiction."
                )
                if f.uncertainty:
                    if jurisdiction_note not in f.uncertainty:
                        f.uncertainty = f"{f.uncertainty} {jurisdiction_note}"
                else:
                    f.uncertainty = jurisdiction_note
                report.jurisdiction_uncertainty_count += 1

            if any(kw in search_text for kw in _ESCALATION_KEYWORDS):
                f.escalation_required = True
                report.escalations_count += 1

        # d. Ambiguous wording in explicit_text
        for f in resp.findings:
            exp_lower = f.explicit_text.lower()
            if any(kw in exp_lower for kw in _AMBIGUOUS_KEYWORDS):
                ambiguity_note = "Contains ambiguous terms subject to interpretation."
                if f.uncertainty:
                    if ambiguity_note not in f.uncertainty:
                        f.uncertainty = f"{f.uncertainty} {ambiguity_note}"
                else:
                    f.uncertainty = ambiguity_note
                report.ambiguity_uncertainty_count += 1

        # f. Source-type separation
        for f in resp.findings:
            if any(c.source_type == "legislation" for c in f.evidence):
                prefix = "This comes from legislation, not a term of the contract."
                if f.interpretation_or_concern:
                    if not f.interpretation_or_concern.startswith(prefix):
                        f.interpretation_or_concern = (
                            f"{prefix} {f.interpretation_or_concern}"
                        )
                else:
                    f.interpretation_or_concern = prefix
                report.source_separation_count += 1
            elif any(c.source_type == "judgment" for c in f.evidence):
                prefix = (
                    "This comes from a court judgment, not a term of the contract."
                )
                if f.interpretation_or_concern:
                    if not f.interpretation_or_concern.startswith(prefix):
                        f.interpretation_or_concern = (
                            f"{prefix} {f.interpretation_or_concern}"
                        )
                else:
                    f.interpretation_or_concern = prefix
                report.source_separation_count += 1

        # g. Injection flagged note
        if injection_flagged:
            inj_note = "Instruction-like text in the document was ignored."
            if resp.limitation:
                if inj_note not in resp.limitation:
                    resp.limitation = f"{resp.limitation} {inj_note}"
            else:
                resp.limitation = inj_note
            report.injection_flagged = True
            report.actions.append("INJECTION_FLAGGED_NOTE_ADDED")

        return resp, report

    except Exception:
        safe_resp = AgentResponse(
            answer="I cannot provide an answer due to an internal guard error.",
            findings=[],
            evidence_sufficient=False,
            limitation="An internal error occurred during response guarding.",
            professional_review_recommended=True,
            status="abstained",
        )
        return safe_resp, GuardReport(
            intent_kind=intent.kind if hasattr(intent, "kind") else "error",
            actions=["GUARD_EXCEPTION"],
        )
