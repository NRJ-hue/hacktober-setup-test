"""Unit and integration tests for FastAPI backend endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.agent.runtime import MockRuntime, RuntimeUnavailable
from backend.app.config import settings
from backend.app.main import app
from backend.app.storage.session_store import session_store


@pytest.fixture(autouse=True)
def clean_session_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure in-memory stores and runtime environment are clean for each test."""
    monkeypatch.setenv("LEGAL_AGENT_RUNTIME", "mock")
    session_store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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


# --- Health & Upload Tests ---

def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_valid_txt(client: TestClient) -> None:
    content = b"14. Termination of Agreement\nNotice of thirty days is required.\n"
    resp = client.post(
        "/api/documents",
        files={"file": ("lease.txt", content, "text/plain")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ready"
    assert data["page_count"] == 1
    assert data["chunk_count"] >= 1
    assert "document_id" in data


def test_upload_fake_extension_rejected(client: TestClient) -> None:
    # .pdf filename with plain text content lacking PDF header
    content = b"Not a real PDF file."
    resp = client.post(
        "/api/documents",
        files={"file": ("fake.pdf", content, "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "CONTENT_TYPE_MISMATCH"


def test_upload_oversized_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    content = b"x" * 200
    monkeypatch.setattr(settings, "max_upload_bytes", 50)
    resp = client.post(
        "/api/documents",
        files={"file": ("big.txt", content, "text/plain")},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "FILE_TOO_LARGE"


def test_upload_scanned_or_empty_pdf_gives_ocr_required(client: TestClient) -> None:
    blank_pdf = make_blank_pdf()
    resp = client.post(
        "/api/documents",
        files={"file": ("empty.pdf", blank_pdf, "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "OCR_REQUIRED"


# --- Question & Interface B Tests ---

def test_ask_question_returns_interface_b_keys(client: TestClient) -> None:
    content = (
        b"14. Termination of Agreement\n"
        b"The notice period for terminating this lease agreement is thirty days.\n"
    )
    up_resp = client.post(
        "/api/documents",
        files={"file": ("contract.txt", content, "text/plain")},
    )
    doc_id = up_resp.json()["document_id"]

    q_resp = client.post(
        f"/api/documents/{doc_id}/questions",
        json={"question": "What is the notice period for terminating the lease?"},
    )
    assert q_resp.status_code == 200
    res = q_resp.json()

    # Interface B AgentResponse keys
    expected_response_keys = {
        "answer",
        "findings",
        "evidence_sufficient",
        "limitation",
        "professional_review_recommended",
        "status",
    }
    assert expected_response_keys.issubset(res.keys())

    # Check finding keys if findings exist
    expected_finding_keys = {
        "title",
        "category",
        "explicit_text",
        "plain_language_explanation",
        "interpretation_or_concern",
        "evidence",
        "uncertainty",
        "escalation_required",
    }
    for finding in res["findings"]:
        assert expected_finding_keys.issubset(finding.keys())


def test_question_too_long_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    content = b"14. Termination\nNotice of thirty days.\n"
    up_resp = client.post(
        "/api/documents",
        files={"file": ("contract.txt", content, "text/plain")},
    )
    doc_id = up_resp.json()["document_id"]

    monkeypatch.setattr(settings, "max_question_chars", 20)
    q_resp = client.post(
        f"/api/documents/{doc_id}/questions",
        json={"question": "This question exceeds the twenty character maximum."},
    )
    assert q_resp.status_code == 400
    assert q_resp.json()["detail"] == "QUESTION_TOO_LONG"


def test_empty_question_rejected(client: TestClient) -> None:
    content = b"14. Termination\nNotice of thirty days.\n"
    up_resp = client.post(
        "/api/documents",
        files={"file": ("contract.txt", content, "text/plain")},
    )
    doc_id = up_resp.json()["document_id"]

    q_resp = client.post(
        f"/api/documents/{doc_id}/questions",
        json={"question": "   "},
    )
    assert q_resp.status_code in (400, 422)


def test_unknown_document_id_returns_404(client: TestClient) -> None:
    bad_id = "00000000000000000000000000000000"
    get_resp = client.get(f"/api/documents/{bad_id}")
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "DOCUMENT_NOT_FOUND"

    ask_resp = client.post(
        f"/api/documents/{bad_id}/questions",
        json={"question": "What is the notice period?"},
    )
    assert ask_resp.status_code == 404
    assert ask_resp.json()["detail"] == "DOCUMENT_NOT_FOUND"

    del_resp = client.delete(f"/api/documents/{bad_id}")
    assert del_resp.status_code == 404
    assert del_resp.json()["detail"] == "DOCUMENT_NOT_FOUND"


def test_delete_document_then_get_and_ask_both_404(client: TestClient) -> None:
    content = b"14. Termination\nNotice of thirty days.\n"
    up_resp = client.post(
        "/api/documents",
        files={"file": ("contract.txt", content, "text/plain")},
    )
    doc_id = up_resp.json()["document_id"]

    # Delete
    del_resp = client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 200

    # GET is 404
    get_resp = client.get(f"/api/documents/{doc_id}")
    assert get_resp.status_code == 404

    # Ask is 404
    ask_resp = client.post(
        f"/api/documents/{doc_id}/questions",
        json={"question": "What is the notice period?"},
    )
    assert ask_resp.status_code == 404


def test_two_documents_isolated(client: TestClient) -> None:
    docA_text = b"1. Apple Orchard Terms\nMaintenance of apple trees and harvest schedule.\n"
    docB_text = b"1. Banana Plantation Terms\nShipping container logistics for bananas.\n"

    upA = client.post("/api/documents", files={"file": ("docA.txt", docA_text, "text/plain")})
    upB = client.post("/api/documents", files={"file": ("docB.txt", docB_text, "text/plain")})

    idA = upA.json()["document_id"]
    idB = upB.json()["document_id"]

    # Ask Doc A about bananas
    askA = client.post(f"/api/documents/{idA}/questions", json={"question": "What are the banana shipping terms?"})
    assert askA.status_code == 200
    resA = askA.json()
    # Evidence must never come from Doc B
    for finding in resA.get("findings", []):
        for citation in finding.get("evidence", []):
            assert not citation.get("source_id", "").startswith(idB)

    # Deleting Doc A does not affect Doc B
    client.delete(f"/api/documents/{idA}")
    getB = client.get(f"/api/documents/{idB}")
    assert getB.status_code == 200


def test_runtime_failure_returns_generic_error_no_leak(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = (
        b"14. Termination\nThe notice period for terminating the lease is thirty days.\n"
        b"15. Payment\nRent is payable monthly.\n"
    )
    up_resp = client.post(
        "/api/documents",
        files={"file": ("contract.txt", content, "text/plain")},
    )
    doc_id = up_resp.json()["document_id"]

    # Mock runtime to raise RuntimeUnavailable
    class FailingRuntime:
        def generate(self, system: str, user: str) -> str:
            raise RuntimeUnavailable("SECRET_INTERNAL_ENGINE_FAILURE")

    monkeypatch.setattr("backend.app.api.questions.get_runtime", lambda: FailingRuntime())

    ask_resp = client.post(
        f"/api/documents/{doc_id}/questions",
        json={"question": "What is the notice period?"},
    )
    assert ask_resp.status_code == 200
    res = ask_resp.json()

    assert res["status"] == "error"
    # Verify no internal exception reason leaked to user
    assert "SECRET_INTERNAL_ENGINE_FAILURE" not in res["answer"]
    assert "SECRET_INTERNAL_ENGINE_FAILURE" not in (res["limitation"] or "")


def test_cors_headers(client: TestClient) -> None:
    # Configured origin: http://localhost:5173
    resp_allowed = client.options(
        "/api/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp_allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Disallowed origin: http://evil.com
    resp_disallowed = client.options(
        "/api/documents",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp_disallowed.headers.get("access-control-allow-origin") is None


def test_no_document_text_in_error_responses(client: TestClient) -> None:
    secret_text = "CONFIDENTIAL_PATENT_SECRET"
    bad_pdf_with_secret = f"%PDF-1.4 {secret_text} broken".encode("utf-8")

    resp = client.post(
        "/api/documents",
        files={"file": ("bad.pdf", bad_pdf_with_secret, "application/pdf")},
    )
    assert resp.status_code == 400
    # Error response body must not leak document text
    assert secret_text not in resp.text
