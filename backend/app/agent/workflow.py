"""Main agent workflow orchestrating prompts, LLM runtime, citation validation, and response guards."""
from __future__ import annotations

import logging
from typing import Optional

from backend.app.agent.prompts import RETRY_SUFFIX, SYSTEM_PROMPT, build_user_prompt
from backend.app.agent.runtime import (
    LLMRuntime,
    MockRuntime,
    ParseFailure,
    RuntimeUnavailable,
    parse_model_output,
)
from backend.app.models.schemas import AgentRequest, AgentResponse
from backend.app.safety.citation_validator import (
    backfill_citation_metadata,
    validate_response,
)
from backend.app.safety.response_guard import (
    classify_question,
    detect_injection,
    enforce_guard,
)

logger = logging.getLogger(__name__)


def run_agent(
    request: AgentRequest,
    runtime: Optional[LLMRuntime] = None,
) -> AgentResponse:
    """Run the legal triage agent workflow end-to-end. Never raises."""
    try:
        # Step a: Classify question & scan all passages for prompt injection
        intent = classify_question(request.question)
        suspicious_ids: set[str] = set()
        for p in request.evidence:
            inj_report = detect_injection(p.text)
            if inj_report.flagged:
                suspicious_ids.add(p.source_id)

        injection_flagged = len(suspicious_ids) > 0

        # Step b: If evidence is insufficient or empty, abstain without calling LLM
        if not request.evidence_sufficient or not request.evidence:
            logger.info("ABSTAIN_INSUFFICIENT_EVIDENCE")
            return AgentResponse(
                answer="The document does not appear to address this question based on available evidence.",
                findings=[],
                evidence_sufficient=False,
                limitation="The document does not appear to address this.",
                professional_review_recommended=True,
                status="abstained",
            )

        # Step c: Use default MockRuntime if not provided
        if runtime is None:
            runtime = MockRuntime("good")

        user_prompt = build_user_prompt(request, suspicious_ids=suspicious_ids)
        try:
            raw_output = runtime.generate(SYSTEM_PROMPT, user_prompt)
        except RuntimeUnavailable:
            logger.error("RUNTIME_UNAVAILABLE")
            return AgentResponse(
                answer="The local model is currently unavailable.",
                findings=[],
                evidence_sufficient=False,
                limitation="The local model is unavailable.",
                professional_review_recommended=True,
                status="error",
            )
        except Exception:
            logger.error("RUNTIME_ERROR")
            return AgentResponse(
                answer="The local model is currently unavailable.",
                findings=[],
                evidence_sufficient=False,
                limitation="The local model is unavailable.",
                professional_review_recommended=True,
                status="error",
            )

        # Step d: Parse output, retry ONCE on ParseFailure
        parsed = parse_model_output(raw_output)
        if isinstance(parsed, ParseFailure):
            logger.warning("PARSE_FAILURE_RETRY")
            retry_prompt = user_prompt + RETRY_SUFFIX
            try:
                raw_retry = runtime.generate(SYSTEM_PROMPT, retry_prompt)
            except RuntimeUnavailable:
                logger.error("RUNTIME_UNAVAILABLE_ON_RETRY")
                return AgentResponse(
                    answer="The local model is currently unavailable.",
                    findings=[],
                    evidence_sufficient=False,
                    limitation="The local model is unavailable.",
                    professional_review_recommended=True,
                    status="error",
                )
            except Exception:
                logger.error("RUNTIME_ERROR_ON_RETRY")
                return AgentResponse(
                    answer="The local model is currently unavailable.",
                    findings=[],
                    evidence_sufficient=False,
                    limitation="The local model is unavailable.",
                    professional_review_recommended=True,
                    status="error",
                )

            parsed = parse_model_output(raw_retry)
            if isinstance(parsed, ParseFailure):
                logger.error("PARSE_FAILURE_FINAL")
                return AgentResponse(
                    answer="The model returned an unreadable answer.",
                    findings=[],
                    evidence_sufficient=False,
                    limitation="The model returned an unreadable answer.",
                    professional_review_recommended=True,
                    status="error",
                )

        # Untrusted injection citations are removed from findings before verification
        if suspicious_ids:
            for finding in parsed.findings:
                finding.evidence = [
                    c for c in finding.evidence if c.source_id not in suspicious_ids
                ]

        # Step e: backfill metadata, validate citations, enforce safety guards
        backfilled = backfill_citation_metadata(parsed, request)
        validated, _ = validate_response(backfilled, request)
        guarded, _ = enforce_guard(
            validated, request, intent, injection_flagged=injection_flagged
        )

        logger.info("AGENT_RUN_SUCCESS")
        return guarded

    except Exception:
        logger.error("WORKFLOW_UNEXPECTED_EXCEPTION")
        return AgentResponse(
            answer="I cannot provide an answer due to an internal system error.",
            findings=[],
            evidence_sufficient=False,
            limitation="An internal error occurred during processing.",
            professional_review_recommended=True,
            status="error",
        )
