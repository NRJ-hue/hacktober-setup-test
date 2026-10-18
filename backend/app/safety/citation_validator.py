"""Citation and finding validator for the legal document triage agent."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NamedTuple

from backend.app.models.schemas import (
    AgentRequest,
    AgentResponse,
    Citation,
    EvidencePassage,
    Finding,
)

_UNICODE_TRANSLATIONS = str.maketrans({
    "\u2018": "'",  # left single quotation mark
    "\u2019": "'",  # right single quotation mark
    "\u201a": "'",  # single low-9 quotation mark
    "\u201b": "'",  # single high-reversed-9 quotation mark
    "\u201c": '"',  # left double quotation mark
    "\u201d": '"',  # right double quotation mark
    "\u201e": '"',  # double low-9 quotation mark
    "\u201f": '"',  # double high-reversed-9 quotation mark
    "\u00ab": '"',  # left-pointing double angle quotation mark
    "\u00bb": '"',  # right-pointing double angle quotation mark
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
})


def normalize_text(s: str) -> str:
    """Collapse whitespace runs, map curly quotes and dashes to ASCII, and strip. Preserves case."""
    if not s:
        return ""
    translated = s.translate(_UNICODE_TRANSLATIONS)
    return re.sub(r"\s+", " ", translated).strip()


class CitationCheck(NamedTuple):
    """Result of verifying a citation against available evidence."""

    ok: bool
    reason: str


@dataclass
class ValidationReport:
    """Summary report of citation and finding validation results."""

    dropped_finding_indices: list[int] = field(default_factory=list)
    failures: list[tuple[int, str]] = field(default_factory=list)
    total_findings: int = 0
    kept_findings: int = 0
    dropped_findings: int = 0
    verified_citations: int = 0
    removed_citations: int = 0


def verify_citation(
    citation: Citation,
    evidence_by_id: Mapping[str, EvidencePassage],
) -> CitationCheck:
    """Verify a single citation against available evidence passages."""
    # 1. UNKNOWN_SOURCE_ID
    if citation.source_id not in evidence_by_id:
        return CitationCheck(ok=False, reason="UNKNOWN_SOURCE_ID")

    evidence = evidence_by_id[citation.source_id]

    # 2. SOURCE_TYPE_MISMATCH
    if evidence.source_type != citation.source_type:
        return CitationCheck(ok=False, reason="SOURCE_TYPE_MISMATCH")

    # 3. PAGE_MISMATCH (only compared when evidence provides it)
    if evidence.page is not None and citation.page != evidence.page:
        return CitationCheck(ok=False, reason="PAGE_MISMATCH")

    # 4. SECTION_MISMATCH (only compared when evidence provides it)
    if evidence.section is not None and citation.section != evidence.section:
        return CitationCheck(ok=False, reason="SECTION_MISMATCH")

    # 5. QUOTE_TOO_SHORT (<8 chars normalized)
    raw_quote = citation.quote
    has_ellipsis = "..." in raw_quote or "\u2026" in raw_quote

    if has_ellipsis:
        raw_segments = re.split(r"\.\.\.|\u2026", raw_quote)
        segments = [normalize_text(seg) for seg in raw_segments if seg.strip()]
        if not segments or any(len(seg) < 8 for seg in segments):
            return CitationCheck(ok=False, reason="QUOTE_TOO_SHORT")
    else:
        norm_quote = normalize_text(raw_quote)
        if len(norm_quote) < 8:
            return CitationCheck(ok=False, reason="QUOTE_TOO_SHORT")
        segments = [norm_quote]

    # 6. QUOTE_NOT_FOUND
    norm_text = normalize_text(evidence.text)
    current_pos = 0
    for seg in segments:
        idx = norm_text.find(seg, current_pos)
        if idx == -1:
            return CitationCheck(ok=False, reason="QUOTE_NOT_FOUND")
        current_pos = idx + len(seg)

    # 7. OK
    return CitationCheck(ok=True, reason="OK")


def backfill_citation_metadata(
    response: AgentResponse,
    request: AgentRequest,
) -> AgentResponse:
    """Backfill citation metadata (source_type, page, section) from evidence passages.

    Citations with unknown source_id are left unchanged so they fail verification.
    Returns a deep copy.
    """
    copy_resp = response.model_copy(deep=True)
    evidence_by_id = {p.source_id: p for p in request.evidence}

    for finding in copy_resp.findings:
        for citation in finding.evidence:
            if citation.source_id in evidence_by_id:
                ev = evidence_by_id[citation.source_id]
                citation.source_type = ev.source_type
                citation.page = ev.page
                citation.section = ev.section

    return copy_resp


def validate_response(
    response: AgentResponse,
    request: AgentRequest,
) -> tuple[AgentResponse, ValidationReport]:
    """Validate citations and findings in an AgentResponse against the AgentRequest.

    Returns deep copy of response and a ValidationReport. Never mutates inputs.
    """
    try:
        # Pass-through: if incoming status is "refused", "abstained" or "error" and there are no findings, return unchanged.
        if response.status in ("refused", "abstained", "error") and len(response.findings) == 0:
            return response.model_copy(deep=True), ValidationReport()

        resp = backfill_citation_metadata(response, request)
        evidence_by_id = {p.source_id: p for p in request.evidence}

        report = ValidationReport(
            total_findings=len(resp.findings),
        )

        kept_findings: list[Finding] = []

        for idx, finding in enumerate(resp.findings):
            verified_citations: list[Citation] = []
            for citation in finding.evidence:
                check = verify_citation(citation, evidence_by_id)
                if check.ok:
                    citation.verified = True
                    verified_citations.append(citation)
                    report.verified_citations += 1
                else:
                    report.removed_citations += 1
                    report.failures.append((idx, check.reason))

            finding.evidence = verified_citations

            # 1. No verified citation
            if not verified_citations:
                report.dropped_finding_indices.append(idx)
                report.failures.append((idx, "NO_VERIFIED_CITATIONS"))
                continue

            # 2. explicit_text shorter than 12 chars normalized
            norm_explicit = normalize_text(finding.explicit_text)
            if len(norm_explicit) < 12:
                report.dropped_finding_indices.append(idx)
                report.failures.append((idx, "EXPLICIT_TEXT_TOO_SHORT"))
                continue

            # 3. explicit_text must be substring of normalized text of a verified passage
            is_substring_of_verified_passage = any(
                norm_explicit in normalize_text(evidence_by_id[c.source_id].text)
                for c in verified_citations
                if c.source_id in evidence_by_id
            )
            if not is_substring_of_verified_passage:
                report.dropped_finding_indices.append(idx)
                report.failures.append((idx, "EXPLICIT_TEXT_NOT_IN_PASSAGE"))
                continue

            kept_findings.append(finding)

        report.kept_findings = len(kept_findings)
        report.dropped_findings = len(report.dropped_finding_indices)

        initial_count = len(resp.findings)

        if initial_count > 0 and len(kept_findings) == 0:
            resp.status = "abstained"
            resp.findings = []
            resp.limitation = "No verifiable evidence supported an answer."
            resp.professional_review_recommended = True
            resp.evidence_sufficient = False
            resp.answer = "I cannot provide an answer because no verifiable evidence was found."
        elif 0 < len(kept_findings) < initial_count and resp.status == "answered":
            resp.findings = kept_findings
            kept_titles = ", ".join(f.title for f in kept_findings)
            resp.answer = f"The document addresses: {kept_titles}."
        else:
            resp.findings = kept_findings

        return resp, report

    except Exception:
        safe_response = AgentResponse(
            answer="I cannot provide an answer due to an internal validation error.",
            findings=[],
            evidence_sufficient=False,
            limitation="An internal error occurred during response verification.",
            professional_review_recommended=True,
            status="abstained",
        )
        report = ValidationReport(
            failures=[(-1, "UNEXPECTED_EXCEPTION")],
            total_findings=len(response.findings) if hasattr(response, "findings") else 0,
            dropped_findings=len(response.findings) if hasattr(response, "findings") else 0,
        )
        return safe_response, report
