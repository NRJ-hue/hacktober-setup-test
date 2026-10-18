"""Document ingestion service orchestrating validation, extraction, and chunking."""
from __future__ import annotations

import logging
from typing import Literal
from pydantic import BaseModel, Field

from backend.app.document.chunker import chunk_document
from backend.app.ingestion.pdf_parser import PdfExtractFailure, extract_pdf
from backend.app.ingestion.txt_parser import extract_txt
from backend.app.ingestion.validator import validate_upload
from backend.app.models.schemas import DocumentChunk, ExtractedPage, SourceType

logger = logging.getLogger(__name__)

IngestStatus = Literal["ready", "failed"]


class IngestResult(BaseModel):
    """Structured result of document ingestion."""

    status: IngestStatus
    reason_code: str
    pages: list[ExtractedPage] = Field(default_factory=list)
    chunks: list[DocumentChunk] = Field(default_factory=list)


def ingest_document(
    document_id: str,
    filename: str,
    data: bytes,
    source_type: SourceType = "contract",
) -> IngestResult:
    """Ingest, validate, extract, and chunk a document.

    Orchestrates validation, PDF/TXT parsing, OCR detection, and clause-aware chunking.
    Never logs or prints document text or filenames. Logs reason codes only.
    """
    try:
        val = validate_upload(filename, data)
        if not val.ok:
            logger.warning("INGESTION_VALIDATION_FAILED")
            return IngestResult(
                status="failed",
                reason_code=val.reason_code,
                pages=[],
                chunks=[],
            )

        if val.kind == "pdf":
            extract_res = extract_pdf(document_id, data)
            if isinstance(extract_res, PdfExtractFailure) or not getattr(
                extract_res, "ok", True
            ):
                logger.warning("INGESTION_EXTRACTION_FAILED")
                return IngestResult(
                    status="failed",
                    reason_code=extract_res.reason_code,
                    pages=[],
                    chunks=[],
                )
            pages = list(extract_res)
        elif val.kind == "txt":
            pages = extract_txt(document_id, data)
        else:
            return IngestResult(
                status="failed",
                reason_code="UNSUPPORTED_FILE_TYPE",
                pages=[],
                chunks=[],
            )

        if not pages:
            logger.warning("INGESTION_NO_PAGES_EXTRACTED")
            return IngestResult(
                status="failed",
                reason_code="NO_PAGES_EXTRACTED",
                pages=[],
                chunks=[],
            )

        chunks = chunk_document(document_id, pages, source_type=source_type)
        if not chunks:
            logger.warning("INGESTION_NO_CHUNKS_PRODUCED")
            return IngestResult(
                status="failed",
                reason_code="NO_CHUNKS_PRODUCED",
                pages=pages,
                chunks=[],
            )

        logger.info("INGESTION_SUCCESS")
        return IngestResult(
            status="ready",
            reason_code="OK",
            pages=pages,
            chunks=chunks,
        )

    except Exception:
        logger.error("INGESTION_UNEXPECTED_EXCEPTION")
        return IngestResult(
            status="failed",
            reason_code="INGESTION_ERROR",
            pages=[],
            chunks=[],
        )
