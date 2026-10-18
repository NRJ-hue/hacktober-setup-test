"""Document management API endpoints for upload, retrieval status, and deletion."""
from __future__ import annotations

import logging
import uuid
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.app.config import settings
from backend.app.ingestion.service import ingest_document
from backend.app.models.schemas import DocumentStatus
from backend.app.storage.session_store import retrieval_service, session_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.post(
    "/documents",
    response_model=DocumentStatus,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(file: UploadFile = File(...)) -> DocumentStatus:
    """Upload and ingest a legal document (PDF or TXT).

    Validates file content, parses pages, chunks content, and stores chunks
    in the in-memory retrieval index. Discards uploaded raw bytes immediately.
    Never logs document text or filenames.
    """
    CHUNK_SIZE = 64 * 1024
    chunks: list[bytes] = []
    total_bytes = 0

    try:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > settings.max_upload_bytes:
                logger.warning("DOCUMENT_UPLOAD_FILE_TOO_LARGE")
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="FILE_TOO_LARGE",
                )
            chunks.append(chunk)
    except HTTPException:
        raise
    except Exception:
        logger.warning("DOCUMENT_UPLOAD_READ_FAILED")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FILE_READ_FAILED",
        )

    data = b"".join(chunks)
    del chunks

    document_id = uuid.uuid4().hex
    filename = file.filename or ""

    ingest_res = ingest_document(
        document_id=document_id,
        filename=filename,
        data=data,
        source_type="contract",
    )

    # Discard raw bytes explicitly
    del data

    if ingest_res.status == "failed":
        session_store.set(
            document_id=document_id,
            status="failed",
            message=ingest_res.reason_code,
        )
        if ingest_res.reason_code == "FILE_TOO_LARGE":
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=ingest_res.reason_code,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ingest_res.reason_code,
        )

    retrieval_service.add_document(document_id, ingest_res.chunks)

    doc_status = session_store.set(
        document_id=document_id,
        status="ready",
        page_count=len(ingest_res.pages),
        chunk_count=len(ingest_res.chunks),
    )

    logger.info("DOCUMENT_UPLOAD_SUCCESS")
    return doc_status


@router.get(
    "/documents/{document_id}",
    response_model=DocumentStatus,
    status_code=status.HTTP_200_OK,
)
def get_document_status(document_id: str) -> DocumentStatus:
    """Retrieve document processing status and metadata."""
    doc_status = session_store.get(document_id)
    if not doc_status or doc_status.status == "deleted":
        logger.warning("DOCUMENT_NOT_FOUND")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DOCUMENT_NOT_FOUND",
        )
    return doc_status


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
)
def delete_document(document_id: str) -> dict[str, str]:
    """Delete a document, dropping its retrieval index and store entry."""
    doc_status = session_store.get(document_id)
    if not doc_status or doc_status.status == "deleted":
        logger.warning("DOCUMENT_DELETE_NOT_FOUND")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DOCUMENT_NOT_FOUND",
        )

    retrieval_service.delete_document(document_id)
    session_store.delete(document_id)

    logger.info("DOCUMENT_DELETED_SUCCESS")
    return {"status": "deleted", "document_id": document_id}
