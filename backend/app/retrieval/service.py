"""In-memory retrieval service orchestrating document indexing and evidence assembly."""
from __future__ import annotations

import logging
from typing import Callable

from backend.app.models.schemas import (
    DocumentChunk,
    EvidencePassage,
    RetrievalResponse,
    SourceType,
)
from backend.app.retrieval.base import ChunkSearcher
from backend.app.retrieval.bm25 import Bm25Index

logger = logging.getLogger(__name__)

# NOTE: BM25 scores are lexical relevance rankings, not probabilities or legal confidence assessments.
DEFAULT_MIN_SCORE: float = 0.5


class RetrievalService:
    """In-memory document retrieval service supporting pluggable searcher backends."""

    def __init__(
        self,
        searcher_factory: Callable[[list[DocumentChunk]], ChunkSearcher] = Bm25Index,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> None:
        self.searcher_factory = searcher_factory
        self.min_score = min_score
        self._documents: dict[str, list[DocumentChunk]] = {}
        self._searchers: dict[str, ChunkSearcher] = {}

    def add_document(self, document_id: str, chunks: list[DocumentChunk]) -> None:
        """Index a document's chunks using the configured searcher backend."""
        self._documents[document_id] = list(chunks)
        self._searchers[document_id] = self.searcher_factory(list(chunks))
        logger.info("RETRIEVAL_DOCUMENT_INDEXED")

    def delete_document(self, document_id: str) -> None:
        """Drop the index and all chunks completely for a document."""
        self._documents.pop(document_id, None)
        self._searchers.pop(document_id, None)
        logger.info("RETRIEVAL_DOCUMENT_DELETED")

    def retrieve(
        self,
        document_id: str,
        question: str,
        top_k: int = 5,
        source_types: tuple[SourceType, ...] = ("contract",),
    ) -> RetrievalResponse:
        """Search chunks of a single document and return assembled EvidencePassages.

        Never returns another document's chunks.
        Filters by allowed source_types.
        evidence_sufficient is False if no results, top score <= min_score, or no question term matches.
        Unknown document_id returns empty evidence and evidence_sufficient=False without raising.
        """
        clean_q = (
            question.strip()
            if isinstance(question, str) and question.strip()
            else ""
        )

        if not clean_q:
            logger.warning("RETRIEVAL_EMPTY_QUESTION")
            return RetrievalResponse(
                document_id=(
                    document_id
                    if document_id and document_id.strip()
                    else "unknown"
                ),
                question="[empty]",
                evidence=[],
                evidence_sufficient=False,
            )

        if document_id not in self._documents or document_id not in self._searchers:
            logger.warning("RETRIEVAL_UNKNOWN_DOCUMENT")
            return RetrievalResponse(
                document_id=document_id,
                question=clean_q,
                evidence=[],
                evidence_sufficient=False,
            )

        searcher = self._searchers[document_id]
        total_chunks = len(self._documents[document_id])

        # Retrieve scored chunks across all chunks of this document to avoid missing valid source_types
        scored_results = searcher.search(clean_q, top_k=total_chunks)

        # Filter by allowed source_types
        filtered = [
            (chunk, score)
            for chunk, score in scored_results
            if chunk.source_type in source_types
        ]

        if not filtered:
            logger.info("RETRIEVAL_NO_MATCHES")
            return RetrievalResponse(
                document_id=document_id,
                question=clean_q,
                evidence=[],
                evidence_sufficient=False,
            )

        top_score = filtered[0][1]

        # Sufficiency criteria: top score must exceed min_score and be strictly positive
        evidence_sufficient = bool(top_score > self.min_score and top_score > 0.0)

        passages = [
            EvidencePassage(
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                page=chunk.page,
                section=chunk.section,
                text=chunk.text,
            )
            for chunk, _ in filtered[:top_k]
        ]

        logger.info("RETRIEVAL_SUCCESS")
        return RetrievalResponse(
            document_id=document_id,
            question=clean_q,
            evidence=passages,
            evidence_sufficient=evidence_sufficient,
        )
