"""Question asking and answer generation API endpoints."""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status

from backend.app.agent.workflow import get_runtime, run_agent
from backend.app.config import settings
from backend.app.models.schemas import AgentRequest, AgentResponse, QuestionRequest
from backend.app.storage.session_store import retrieval_service, session_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["questions"])


@router.post(
    "/documents/{document_id}/questions",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
)
def ask_question(document_id: str, payload: QuestionRequest) -> AgentResponse:
    """Ask a question about an ingested legal document.

    Validates question length, retrieves relevant passages via lexical search,
    and runs the agent triage workflow with the active runtime.
    """
    doc_status = session_store.get(document_id)
    if not doc_status or doc_status.status == "deleted":
        logger.warning("QUESTION_DOCUMENT_NOT_FOUND")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DOCUMENT_NOT_FOUND",
        )

    question_text = payload.question.strip()
    if not question_text:
        logger.warning("QUESTION_EMPTY")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMPTY_QUESTION",
        )

    if len(question_text) > settings.max_question_chars:
        logger.warning("QUESTION_TOO_LONG")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QUESTION_TOO_LONG",
        )

    retrieval_res = retrieval_service.retrieve(
        document_id=document_id,
        question=question_text,
    )

    agent_req = AgentRequest(
        document_id=retrieval_res.document_id,
        question=retrieval_res.question,
        evidence=retrieval_res.evidence,
        evidence_sufficient=retrieval_res.evidence_sufficient,
    )

    runtime = get_runtime()
    response = run_agent(agent_req, runtime=runtime)

    logger.info("QUESTION_ANSWER_SUCCESS")
    return response
