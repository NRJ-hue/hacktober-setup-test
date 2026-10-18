"""Unit tests for document upload validation, PDF/TXT parsing, and ingestion service."""
from __future__ import annotations

import pytest

from backend.app.ingestion.normalizer import normalize_for_search
from backend.app.ingestion.pdf_parser import PdfExtractFailure, extract_pdf
from backend.app.ingestion.service import IngestResult, ingest_document
from backend.app.ingestion.txt_parser import extract_txt
from backend.app.ingestion.validator import validate_upload
from backend.app.models.schemas import ExtractedPage


def make_minimal_pdf(text: str) -> bytes:
    """Construct a minimal valid PDF byte sequence containing text."""
    stream_content = f"BT\n/F1 12 Tf\n72 712 Td\n({text}) Tj\nET\n".encode("latin1")
    stream_len = len(stream_content)

    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"5 0 obj\n<< /Length " + str(stream_len).encode("ascii") + b" >>\nstream\n"
        + stream_content
        + b"endstream\nendobj\n"
    )

    o1 = 9
    o2 = body.find(b"2 0 obj")
    o3 = body.find(b"3 0 obj")
    o4 = body.find(b"4 0 obj")
    o5 = body.find(b"5 0 obj")
    xref_offset = len(body)

    xref = (
        f"xref\n0 6\n"
        f"0000000000 65535 f \n"
        f"{o1:010d} 00000 n \n"
        f"{o2:010d} 00000 n \n"
        f"{o3:010d} 00000 n \n"
        f"{o4:010d} 00000 n \n"
        f"{o5:010d} 00000 n \n"
        f"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")

    return body + xref


def make_blank_pdf() -> bytes:
    """Construct a minimal valid PDF byte sequence with no extractable text."""
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << >> /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 0 >>\nstream\n"
        b"endstream\nendobj\n"
    )
    xref_offset = len(body)
    o1 = 9
    o2 = body.find(b"2 0 obj")
    o3 = body.find(b"3 0 obj")
    o4 = body.find(b"4 0 obj")
    xref = (
        f"xref\n0 5\n"
        f"0000000000 65535 f \n"
        f"{o1:010d} 00000 n \n"
        f"{o2:010d} 00000 n \n"
        f"{o3:010d} 00000 n \n"
        f"{o4:010d} 00000 n \n"
        f"trailer\n<< /Size 5 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return body + xref


# --- Validator Tests ---

def test_validate_upload_valid_pdf() -> None:
    data = make_minimal_pdf("This is a valid PDF text with enough characters to pass extraction.")
    res = validate_upload("document.pdf", data)
    assert res.ok is True
    assert res.kind == "pdf"
    assert res.reason_code == "OK"


def test_validate_upload_valid_txt() -> None:
    data = b"Plain text file content for legal agreement."
    res = validate_upload("contract.txt", data)
    assert res.ok is True
    assert res.kind == "txt"
    assert res.reason_code == "OK"


def test_validate_upload_fake_pdf_with_txt_content_rejected() -> None:
    # Has .pdf extension but lacks %PDF- header
    data = b"This is plain text pretending to be a PDF."
    res = validate_upload("fake.pdf", data)
    assert res.ok is False
    assert res.kind is None
    assert res.reason_code == "CONTENT_TYPE_MISMATCH"


def test_validate_upload_empty_file_rejected() -> None:
    res = validate_upload("empty.pdf", b"")
    assert res.ok is False
    assert res.kind is None
    assert res.reason_code == "EMPTY_FILE"


def test_validate_upload_oversized_file_rejected() -> None:
    data = b"a" * 100
    res = validate_upload("big.txt", data, max_bytes=50)
    assert res.ok is False
    assert res.kind is None
    assert res.reason_code == "FILE_TOO_LARGE"


def test_validate_upload_unsupported_extension_rejected() -> None:
    data = b"%PDF-1.4 dummy"
    res = validate_upload("document.doc", data)
    assert res.ok is False
    assert res.kind is None
    assert res.reason_code == "UNSUPPORTED_FILE_TYPE"


def test_validate_upload_txt_with_nul_bytes_rejected() -> None:
    data = b"Some valid text\x00corrupt binary bytes"
    res = validate_upload("corrupt.txt", data)
    assert res.ok is False
    assert res.kind is None
    assert res.reason_code == "CONTAINS_NUL_BYTES"


def test_validate_upload_txt_invalid_utf8_rejected() -> None:
    data = b"Invalid UTF-8 \xff\xfe bytes"
    res = validate_upload("invalid.txt", data)
    assert res.ok is False
    assert res.kind is None
    assert res.reason_code == "INVALID_UTF8"


# --- PDF Parser Tests ---

def test_extract_pdf_valid_content_and_page_numbers() -> None:
    text = "Valid contract clause text extracted with sufficient character length."
    data = make_minimal_pdf(text)
    pages = extract_pdf("doc-pdf-1", data)

    assert not isinstance(pages, PdfExtractFailure)
    assert len(pages) == 1
    assert pages[0].document_id == "doc-pdf-1"
    assert pages[0].page_number == 1
    assert "Valid contract clause" in pages[0].text


def test_extract_pdf_corrupt_returns_failure_without_raising() -> None:
    corrupt_data = b"%PDF-1.4 corrupt byte stream that is broken %%EOF"
    res = extract_pdf("doc-corrupt", corrupt_data)

    assert isinstance(res, PdfExtractFailure)
    assert res.ok is False
    assert res.reason_code == "CORRUPT_PDF"


def test_extract_pdf_no_text_requires_ocr() -> None:
    blank_data = make_blank_pdf()
    res = extract_pdf("doc-scanned", blank_data)

    assert isinstance(res, PdfExtractFailure)
    assert res.ok is False
    assert res.reason_code == "OCR_REQUIRED"


# --- TXT Parser Tests ---

def test_extract_txt_single_page() -> None:
    data = b"Section 1. Term of agreement.\nTenant agrees to terms."
    pages = extract_txt("doc-txt-1", data)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].document_id == "doc-txt-1"
    assert "Section 1. Term" in pages[0].text


def test_extract_txt_with_form_feed_splits_pages() -> None:
    data = b"Page 1 terms and conditions.\fPage 2 payment details.\fPage 3 termination.\f"
    pages = extract_txt("doc-txt-multi", data)

    assert len(pages) == 3
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert pages[2].page_number == 3
    assert "Page 1" in pages[0].text
    assert "Page 2" in pages[1].text
    assert "Page 3" in pages[2].text


# --- Normalizer Tests ---

def test_normalizer_for_search_lowercases_and_collapses_whitespace() -> None:
    original = "  Section  14.1\n\nTermination   Obligations\t"
    normalized = normalize_for_search(original)

    assert normalized == "section 14.1 termination obligations"
    # Ensure original string was not altered
    assert "Section  14.1" in original


# --- Service Ingestion Tests ---

def test_service_ingest_document_pdf_end_to_end() -> None:
    pdf_text = (
        "14. Termination of Agreement\n"
        "Either party may terminate this agreement upon thirty days written notice.\n"
        "15. Governing Law\n"
        "This agreement shall be governed by the laws of England and Wales."
    )
    data = make_minimal_pdf(pdf_text)
    result = ingest_document("doc-service-pdf", "contract.pdf", data, source_type="contract")

    assert isinstance(result, IngestResult)
    assert result.status == "ready"
    assert result.reason_code == "OK"
    assert len(result.pages) == 1
    assert len(result.chunks) >= 1
    assert all(c.document_id == "doc-service-pdf" for c in result.chunks)
    assert all(c.text in result.pages[0].text for c in result.chunks)


def test_service_ingest_document_txt_with_form_feed() -> None:
    txt_content = (
        "14. Termination\nNotice of thirty days.\f"
        "15. Payment\nPayment due monthly."
    ).encode("utf-8")

    result = ingest_document("doc-service-txt", "lease.txt", txt_content, source_type="contract")

    assert result.status == "ready"
    assert result.reason_code == "OK"
    assert len(result.pages) == 2
    assert len(result.chunks) >= 2


def test_service_ingest_document_validation_failure() -> None:
    result = ingest_document("doc-bad", "fake.pdf", b"Not a real PDF", source_type="contract")

    assert result.status == "failed"
    assert result.reason_code == "CONTENT_TYPE_MISMATCH"
    assert len(result.pages) == 0
    assert len(result.chunks) == 0


def test_service_ingest_document_ocr_required_propagation() -> None:
    blank_data = make_blank_pdf()
    result = ingest_document("doc-scanned", "scanned.pdf", blank_data, source_type="contract")

    assert result.status == "failed"
    assert result.reason_code == "OCR_REQUIRED"
    assert len(result.pages) == 0


def test_no_document_text_in_any_reason_code() -> None:
    reason_codes = [
        validate_upload("a.pdf", b"").reason_code,
        validate_upload("a.pdf", b"not pdf").reason_code,
        validate_upload("a.txt", b"a\x00b").reason_code,
        validate_upload("a.doc", b"data").reason_code,
        extract_pdf("doc", b"%PDF-bad").reason_code,
        extract_pdf("doc", make_blank_pdf()).reason_code,
    ]
    for code in reason_codes:
        # Reason codes must be uppercase alphanumeric with underscores only
        assert code.isupper()
        assert " " not in code
        assert "\n" not in code
