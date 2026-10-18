"""Plain text document parser splitting on form feed or producing single page."""
from __future__ import annotations

import logging
from backend.app.models.schemas import ExtractedPage

logger = logging.getLogger(__name__)


def extract_txt(
    document_id: str,
    data: bytes,
) -> list[ExtractedPage]:
    """Extract ExtractedPage instances from UTF-8 text bytes.

    Splits on form feed ('\f') if present, otherwise returns a single page.
    Page numbers start from 1.
    Logs reason codes only; never logs document text.
    """
    text = data.decode("utf-8")

    if "\f" in text:
        raw_pages = text.split("\f")
        # If trailing form feed produced an empty final element, strip it
        if len(raw_pages) > 1 and not raw_pages[-1].strip():
            raw_pages = raw_pages[:-1]
    else:
        raw_pages = [text]

    pages = [
        ExtractedPage(
            document_id=document_id,
            page_number=idx,
            text=p_text,
        )
        for idx, p_text in enumerate(raw_pages, start=1)
    ]

    logger.info("TXT_PARSER_SUCCESS")
    return pages
