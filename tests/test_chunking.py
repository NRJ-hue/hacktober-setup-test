"""Unit tests for section detection, parent clause detection, and document chunking."""
from __future__ import annotations

import re
import pytest

from backend.app.document.chunker import (
    DEFAULT_WORD_LIMIT,
    DEFAULT_WORD_OVERLAP,
    _detect_parent_clause,
    chunk_document,
)
from backend.app.document.section_detector import detect_sections
from backend.app.models.schemas import ExtractedPage


# --- Section Detection Tests ---

def test_detect_sections_finds_required_headings() -> None:
    sample = (
        "Preamble and recitals.\n"
        "14. Termination of Contract\n"
        "Notice must be given in writing.\n"
        "14.1 Immediate Termination for Cause\n"
        "Immediate termination occurs upon bankruptcy.\n"
        "Section 14 Dispute Resolution\n"
        "All disputes submitted to mediation.\n"
        "Clause 14.1 Confidentiality Terms\n"
        "Parties shall maintain confidentiality.\n"
        "ARTICLE IV GOVERNING LAW\n"
        "Governed by state laws.\n"
    )

    sections = detect_sections(sample)
    labels = [label for _, label in sections]

    assert "14." in labels
    assert "14.1" in labels
    assert "Section 14" in labels
    assert "Clause 14.1" in labels
    assert "ARTICLE IV" in labels

    # Check offsets point to the actual label in sample
    for offset, label in sections:
        assert sample[offset : offset + len(label)] == label


def test_detect_sections_without_structure_returns_empty_list() -> None:
    plain_prose = (
        "The tenant agrees to maintain the garden and keep the premises clean. "
        "Rent is payable on the first day of each calendar month. "
        "A late fee of 3.14 percent or 50 dollars applies if delayed."
    )

    sections = detect_sections(plain_prose)
    assert sections == []


# --- Parent Clause Detection Tests ---

def test_detect_parent_clause() -> None:
    assert _detect_parent_clause("14.") == "14"
    assert _detect_parent_clause("14.1") == "14"
    assert _detect_parent_clause("14.2.3") == "14"
    assert _detect_parent_clause("Section 14") == "14"
    assert _detect_parent_clause("Clause 14.1") == "14"
    assert _detect_parent_clause("ARTICLE IV") == "IV"
    assert _detect_parent_clause(None) is None
    assert _detect_parent_clause("General Provisions") is None


# --- Document Chunking Tests ---

def test_chunking_exact_substring_preservation() -> None:
    page_text = (
        "14. Termination of Agreement\n"
        "Either party may terminate upon 30 days written notice.\n"
        "15. Governing Law\n"
        "This agreement is governed by the laws of California."
    )
    page = ExtractedPage(document_id="doc-sub-1", page_number=1, text=page_text)
    chunks = chunk_document("doc-sub-1", [page], source_type="contract")

    assert len(chunks) >= 2
    for chunk in chunks:
        # Every chunk's text must be an EXACT substring of its page's original text
        assert chunk.text in page.text
        # No synthetic headings inserted
        assert not chunk.text.startswith("HEADER:")
        assert not chunk.text.startswith("[Chunk")


def test_chunking_metadata_and_clause_boundaries() -> None:
    page_text = (
        "14. Termination\n"
        "Notice must be served.\n"
        "14.1 Notice Period\n"
        "Thirty days required."
    )
    page = ExtractedPage(document_id="doc-meta-1", page_number=2, text=page_text)
    chunks = chunk_document("doc-meta-1", [page], source_type="contract")

    assert len(chunks) == 2

    # Chunk 0
    assert chunks[0].document_id == "doc-meta-1"
    assert chunks[0].page == 2
    assert chunks[0].section == "14."
    assert chunks[0].parent_clause_id == "14"
    assert chunks[0].chunk_index == 0
    assert chunks[0].source_id == "doc-meta-1-p2-c0"
    assert chunks[0].chunk_id == "doc-meta-1-p2-c0"
    assert chunks[0].source_type == "contract"

    # Chunk 1
    assert chunks[1].document_id == "doc-meta-1"
    assert chunks[1].page == 2
    assert chunks[1].section == "14.1"
    assert chunks[1].parent_clause_id == "14"
    assert chunks[1].chunk_index == 1
    assert chunks[1].source_id == "doc-meta-1-p2-c1"
    assert chunks[1].chunk_id == "doc-meta-1-p2-c1"
    assert chunks[1].source_type == "contract"


def test_chunking_unstructured_page() -> None:
    plain_text = (
        "This is an unnumbered memorandum regarding commercial real estate leases. "
        "It contains standard expectations and non-binding advice for tenants."
    )
    page = ExtractedPage(document_id="doc-unstruct", page_number=1, text=plain_text)
    chunks = chunk_document("doc-unstruct", [page], source_type="contract")

    assert len(chunks) == 1
    assert chunks[0].section is None
    assert chunks[0].parent_clause_id is None
    assert chunks[0].text in plain_text
    assert chunks[0].source_id == "doc-unstruct-p1-c0"


def test_chunking_overlap_present_on_long_sections() -> None:
    # Build a long section with 260 words
    words = [f"word{i}" for i in range(260)]
    long_clause_text = "Section 14 Long Obligations\n" + " ".join(words)
    page = ExtractedPage(document_id="doc-long", page_number=1, text=long_clause_text)

    chunks = chunk_document("doc-long", [page], source_type="contract")

    # Should split into multiple chunks
    assert len(chunks) >= 2

    # Verify both chunks are exact substrings of original page
    assert chunks[0].text in page.text
    assert chunks[1].text in page.text

    # Verify overlap: consecutive chunks share ~35 words
    chunk0_words = chunks[0].text.split()
    chunk1_words = chunks[1].text.split()

    overlap_words = set(chunk0_words).intersection(set(chunk1_words))
    # Check that overlap is approximately 35 words
    assert len(overlap_words) >= 30


def test_chunking_preserves_document_id_across_all_chunks() -> None:
    p1 = ExtractedPage(document_id="doc-multi-page", page_number=1, text="1. Clause One\nContent.")
    p2 = ExtractedPage(document_id="doc-multi-page", page_number=2, text="2. Clause Two\nContent.")
    chunks = chunk_document("doc-multi-page", [p1, p2], source_type="judgment")

    assert len(chunks) == 2
    assert all(c.document_id == "doc-multi-page" for c in chunks)
    assert all(c.source_type == "judgment" for c in chunks)
    assert chunks[0].source_id == "doc-multi-page-p1-c0"
    assert chunks[1].source_id == "doc-multi-page-p2-c1"
