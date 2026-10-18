"""PDF document text extraction with scanned-PDF detection and structured failure handling."""
from __future__ import annotations

import io
import logging
from pydantic import BaseModel, Field
import pypdf

from backend.app.models.schemas import ExtractedPage

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE_THRESHOLD = 50


class PdfExtractFailure(BaseModel):
    """Structured failure representation for PDF extraction."""

    ok: bool = False
    reason_code: str
    pages: list[ExtractedPage] = Field(default_factory=list)


class PdfExtractSuccess(list):
    """List of ExtractedPage instances with success metadata."""

    ok: bool = True
    reason_code: str = "OK"

    @property
    def pages(self) -> list[ExtractedPage]:
        return list(self)


def extract_pdf(
    document_id: str,
    data: bytes,
) -> list[ExtractedPage] | PdfExtractFailure:
    """Extract physical pages from PDF bytes using pypdf.

    One ExtractedPage per physical page, 1-indexed page_number.
    Never raises on corrupt or encrypted PDF; returns structured PdfExtractFailure.
    Detects scanned PDFs with less than 50 chars/page on average and returns OCR_REQUIRED.
    Logs reason codes only; never logs document text.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
    except Exception:
        logger.warning("PDF_PARSER_CORRUPT_OR_UNREADABLE")
        return PdfExtractFailure(reason_code="CORRUPT_PDF")

    try:
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")
                if decrypted == 0:
                    logger.warning("PDF_PARSER_ENCRYPTED_FILE")
                    return PdfExtractFailure(reason_code="ENCRYPTED_PDF")
            except Exception:
                logger.warning("PDF_PARSER_ENCRYPTED_FILE")
                return PdfExtractFailure(reason_code="ENCRYPTED_PDF")

        num_pages = len(reader.pages)
        if num_pages == 0:
            logger.warning("PDF_PARSER_EMPTY_PAGES")
            return PdfExtractFailure(reason_code="EMPTY_PDF")

        pages: list[ExtractedPage] = []
        for idx, page in enumerate(reader.pages, start=1):
            try:
                extracted = page.extract_text() or ""
            except Exception:
                extracted = ""
            pages.append(
                ExtractedPage(
                    document_id=document_id,
                    page_number=idx,
                    text=extracted,
                )
            )

        total_extracted_chars = sum(len(p.text.strip()) for p in pages)
        avg_chars_per_page = total_extracted_chars / num_pages

        if avg_chars_per_page < MIN_CHARS_PER_PAGE_THRESHOLD:
            logger.warning("PDF_PARSER_OCR_REQUIRED")
            return PdfExtractFailure(reason_code="OCR_REQUIRED")

        logger.info("PDF_PARSER_SUCCESS")
        return PdfExtractSuccess(pages)

    except Exception:
        logger.warning("PDF_PARSER_UNEXPECTED_EXCEPTION")
        return PdfExtractFailure(reason_code="CORRUPT_PDF")
