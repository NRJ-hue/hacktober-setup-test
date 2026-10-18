"""In-memory session store for document metadata and processing status.

LIMITS & SECURITY NOTICE:
State stored here is purely in-memory and ephemeral; all state is lost upon server
restart. A randomly generated document_id (UUID4 hex) provides collision resistance,
but is NOT a substitute for user authentication or authorization controls.
Uploaded raw document bytes are discarded immediately after ingestion, and chunks
are managed exclusively by RetrievalService.
"""
from __future__ import annotations

import logging
from backend.app.models.schemas import DocumentProcessingStatus, DocumentStatus

logger = logging.getLogger(__name__)


class SessionStore:
    """Thread-safe in-memory store for document processing status and metadata."""

    def __init__(self) -> None:
        self._documents: dict[str, DocumentStatus] = {}

    def set(
        self,
        document_id: str,
        status: DocumentProcessingStatus,
        page_count: int | None = None,
        chunk_count: int | None = None,
        message: str | None = None,
    ) -> DocumentStatus:
        """Create or replace status and metadata for a document."""
        doc_status = DocumentStatus(
            document_id=document_id,
            status=status,
            page_count=page_count,
            chunk_count=chunk_count,
            message=message,
        )
        self._documents[document_id] = doc_status
        logger.info("SESSION_STORE_SET")
        return doc_status

    def get(self, document_id: str) -> DocumentStatus | None:
        """Retrieve document status by document_id, or None if unknown/deleted."""
        return self._documents.get(document_id)

    def delete(self, document_id: str) -> bool:
        """Remove document entry from store. Returns True if removed, False if not found."""
        removed = self._documents.pop(document_id, None) is not None
        if removed:
            logger.info("SESSION_STORE_DELETED")
        return removed

    def clear(self) -> None:
        """Clear all stored documents (primarily for testing)."""
        self._documents.clear()


from backend.app.retrieval.service import RetrievalService

session_store = SessionStore()
retrieval_service = RetrievalService()

