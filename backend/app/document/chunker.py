"""Document chunker splitting pages along clause boundaries with exact substring preservation."""
from __future__ import annotations

import logging
import re
from backend.app.document.section_detector import detect_sections
from backend.app.models.schemas import DocumentChunk, ExtractedPage, SourceType

logger = logging.getLogger(__name__)

# NOTE: Target about 200 words per chunk with about 35 words of overlap as a
# PLACEHOLDER for token counts (the embedding tokenizer is not installed yet).
DEFAULT_WORD_LIMIT = 200
DEFAULT_WORD_OVERLAP = 35


def _detect_parent_clause(section: str | None) -> str | None:
    """Extract top-level clause number or Roman numeral from a section label."""
    if not section:
        return None
    # Check for digit-based clause number, e.g. "14", "14.1", "Section 14", "Clause 14.1" -> "14"
    match_num = re.search(r"\b(\d+)", section)
    if match_num:
        return match_num.group(1)
    # Check for Roman numerals, e.g. "ARTICLE IV" -> "IV"
    match_roman = re.search(r"\b([IVXLCDM]+)\b", section, re.IGNORECASE)
    if match_roman:
        return match_roman.group(1).upper()
    return None


def _slice_words(
    text: str,
    block_offset: int,
    word_limit: int = DEFAULT_WORD_LIMIT,
    overlap: int = DEFAULT_WORD_OVERLAP,
) -> list[tuple[int, int]]:
    """Return character span slices (start_char, end_char) for sliding word window.

    Each slice is an exact substring interval of the original page text.
    """
    words = list(re.finditer(r"\S+", text))
    if not words:
        return []

    if len(words) <= word_limit:
        start_char = block_offset + words[0].start()
        end_char = block_offset + words[-1].end()
        return [(start_char, end_char)]

    step = max(1, word_limit - overlap)
    slices: list[tuple[int, int]] = []
    w_start = 0
    while w_start < len(words):
        w_end = min(w_start + word_limit, len(words))
        start_char = block_offset + words[w_start].start()
        end_char = block_offset + words[w_end - 1].end()
        slices.append((start_char, end_char))
        if w_end >= len(words):
            break
        w_start += step

    return slices


def chunk_document(
    document_id: str,
    pages: list[ExtractedPage],
    source_type: SourceType = "contract",
) -> list[DocumentChunk]:
    """Chunk extracted pages preferring clause boundaries with word-level overlap.

    Target about 200 words per chunk with about 35 words of overlap, as a PLACEHOLDER
    for token counts (the embedding tokenizer is not installed yet; note this in a comment).
    Each chunk's text is an EXACT substring of its page's original text (no synthetic headings).
    Sets chunk_id, source_id (f"{document_id}-p{page}-c{index}"), page, section,
    parent_clause_id (top-level clause number if detectable), and chunk_index.
    """
    chunks: list[DocumentChunk] = []
    global_chunk_index = 0

    for page in pages:
        page_text = page.text
        if not page_text or not page_text.strip():
            continue

        sections = detect_sections(page_text)

        # Build blocks: list of (start_char, end_char, section_label, parent_clause_id)
        blocks: list[tuple[int, int, str | None, str | None]] = []

        if not sections:
            # No section structure detected; treat entire page as a single block
            blocks.append((0, len(page_text), None, None))
        else:
            # Preamble before first section if present
            if sections[0][0] > 0:
                preamble_text = page_text[: sections[0][0]]
                if preamble_text.strip():
                    blocks.append((0, sections[0][0], None, None))

            for idx, (sec_start, sec_label) in enumerate(sections):
                sec_end = (
                    sections[idx + 1][0]
                    if idx + 1 < len(sections)
                    else len(page_text)
                )
                parent_id = _detect_parent_clause(sec_label)
                blocks.append((sec_start, sec_end, sec_label, parent_id))

        for block_start, block_end, sec_label, parent_id in blocks:
            block_text = page_text[block_start:block_end]
            if not block_text.strip():
                continue

            slices = _slice_words(block_text, block_start)
            for start_char, end_char in slices:
                chunk_text = page_text[start_char:end_char]
                if not chunk_text.strip():
                    continue

                source_id = f"{document_id}-p{page.page_number}-c{global_chunk_index}"
                chunk = DocumentChunk(
                    chunk_id=source_id,
                    document_id=document_id,
                    source_id=source_id,
                    source_type=source_type,
                    page=page.page_number,
                    section=sec_label,
                    parent_clause_id=parent_id,
                    chunk_index=global_chunk_index,
                    text=chunk_text,
                )
                chunks.append(chunk)
                global_chunk_index += 1

    logger.info("DOCUMENT_CHUNKING_SUCCESS")
    return chunks
