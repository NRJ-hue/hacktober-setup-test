"""Tests for lexical retrieval (BM25), ChunkSearcher protocol, and RetrievalService."""
from __future__ import annotations

import logging
import pytest

from backend.app.agent.runtime import MockRuntime
from backend.app.agent.workflow import run_agent
from backend.app.ingestion.service import ingest_document
from backend.app.models.schemas import (
    AgentRequest,
    DocumentChunk,
    EvidencePassage,
    RetrievalResponse,
    SourceType,
)
from backend.app.retrieval.base import ChunkSearcher
from backend.app.retrieval.bm25 import Bm25Index
from backend.app.retrieval.service import RetrievalService


@pytest.fixture
def sample_chunks() -> list[DocumentChunk]:
    """Synthetic multi-clause document chunks labeled FAKE."""
    return [
        DocumentChunk(
            chunk_id="doc1-p1-c0",
            document_id="doc-lease-1",
            source_id="doc-lease-1-p1-c0",
            source_type="contract",
            page=1,
            section="14. Termination",
            parent_clause_id="14",
            chunk_index=0,
            text="FAKE, illustrative only: The notice period for terminating this lease shall be thirty days written notice.",
        ),
        DocumentChunk(
            chunk_id="doc1-p1-c1",
            document_id="doc-lease-1",
            source_id="doc-lease-1-p1-c1",
            source_type="contract",
            page=1,
            section="15. Security Deposit",
            parent_clause_id="15",
            chunk_index=1,
            text="FAKE, illustrative only: The security deposit of one month rent shall be held in escrow by the landlord.",
        ),
        DocumentChunk(
            chunk_id="doc1-p1-c2",
            document_id="doc-lease-1",
            source_id="doc-lease-1-p1-c2",
            source_type="legislation",
            page=1,
            section="Section 20 Statutory Rules",
            parent_clause_id="20",
            chunk_index=2,
            text="FAKE, illustrative only: Statutory rules govern the maximum allowed interest on held security deposits.",
        ),
    ]


# --- BM25 & RetrievalService Tests ---

def test_top_result_security_deposit(sample_chunks: list[DocumentChunk]) -> None:
    service = RetrievalService()
    service.add_document("doc-lease-1", sample_chunks)

    res = service.retrieve("doc-lease-1", "security deposit")

    assert res.evidence_sufficient is True
    assert len(res.evidence) >= 1
    top = res.evidence[0]
    assert top.source_id == "doc-lease-1-p1-c1"
    assert top.section == "15. Security Deposit"
    assert "security deposit" in top.text.lower()


def test_top_result_notice_period(sample_chunks: list[DocumentChunk]) -> None:
    service = RetrievalService()
    service.add_document("doc-lease-1", sample_chunks)

    res = service.retrieve("doc-lease-1", "notice period")

    assert res.evidence_sufficient is True
    assert len(res.evidence) >= 1
    top = res.evidence[0]
    assert top.source_id == "doc-lease-1-p1-c0"
    assert top.section == "14. Termination"
    assert "notice period" in top.text.lower()


def test_unrelated_question_gives_insufficient_evidence(
    sample_chunks: list[DocumentChunk],
) -> None:
    service = RetrievalService()
    service.add_document("doc-lease-1", sample_chunks)

    res = service.retrieve("doc-lease-1", "who won the football match")

    assert res.evidence_sufficient is False


def test_two_documents_indexed_results_never_cross() -> None:
    docA_chunks = [
        DocumentChunk(
            chunk_id="docA-p1-c0",
            document_id="docA",
            source_id="docA-p1-c0",
            source_type="contract",
            page=1,
            section="Section 1",
            parent_clause_id="1",
            chunk_index=0,
            text="FAKE, illustrative only: Apple orchard maintenance terms and fruit picking schedule.",
        )
    ]
    docB_chunks = [
        DocumentChunk(
            chunk_id="docB-p1-c0",
            document_id="docB",
            source_id="docB-p1-c0",
            source_type="contract",
            page=1,
            section="Section 1",
            parent_clause_id="1",
            chunk_index=0,
            text="FAKE, illustrative only: Banana plantation logistics and shipping container rules.",
        )
    ]

    service = RetrievalService()
    service.add_document("docA", docA_chunks)
    service.add_document("docB", docB_chunks)

    # Searching docA for banana terms must return nothing from docB
    resA = service.retrieve("docA", "banana plantation")
    assert all(p.source_id.startswith("docA") for p in resA.evidence)
    assert not any("banana" in p.text.lower() for p in resA.evidence)

    # Searching docB for apple terms must return nothing from docA
    resB = service.retrieve("docB", "apple orchard")
    assert all(p.source_id.startswith("docB") for p in resB.evidence)
    assert not any("apple" in p.text.lower() for p in resB.evidence)


def test_delete_document_removes_everything(sample_chunks: list[DocumentChunk]) -> None:
    service = RetrievalService()
    service.add_document("doc-lease-1", sample_chunks)

    # Confirm present before deletion
    assert "doc-lease-1" in service._documents
    assert "doc-lease-1" in service._searchers

    service.delete_document("doc-lease-1")

    # Internal structures must hold no chunks or index for the deleted document
    assert "doc-lease-1" not in service._documents
    assert "doc-lease-1" not in service._searchers

    # Subsequent retrieval returns insufficient evidence with empty passages
    res = service.retrieve("doc-lease-1", "security deposit")
    assert res.evidence_sufficient is False
    assert len(res.evidence) == 0


def test_source_type_filter_excludes_legislation_by_default(
    sample_chunks: list[DocumentChunk],
) -> None:
    service = RetrievalService()
    service.add_document("doc-lease-1", sample_chunks)

    # Default source_types=("contract",)
    res_default = service.retrieve("doc-lease-1", "security deposit interest")
    assert all(p.source_type == "contract" for p in res_default.evidence)
    assert not any(p.source_type == "legislation" for p in res_default.evidence)

    # Explicitly include legislation
    res_both = service.retrieve(
        "doc-lease-1",
        "security deposit interest",
        source_types=("contract", "legislation"),
    )
    assert any(p.source_type == "legislation" for p in res_both.evidence)


def test_evidence_text_is_exact_substring_and_metadata_preserved(
    sample_chunks: list[DocumentChunk],
) -> None:
    service = RetrievalService()
    service.add_document("doc-lease-1", sample_chunks)

    res = service.retrieve("doc-lease-1", "notice period")
    assert len(res.evidence) >= 1

    ev = res.evidence[0]
    original_chunk = sample_chunks[0]

    # Exact substring
    assert ev.text == original_chunk.text
    # Exact metadata preserved
    assert ev.source_id == original_chunk.source_id
    assert ev.source_type == original_chunk.source_type
    assert ev.page == original_chunk.page
    assert ev.section == original_chunk.section


def test_unknown_document_handled_without_exception() -> None:
    service = RetrievalService()
    res = service.retrieve("unknown-doc-id", "any question")

    assert res.document_id == "unknown-doc-id"
    assert res.evidence_sufficient is False
    assert res.evidence == []


def test_empty_question_handled(sample_chunks: list[DocumentChunk]) -> None:
    service = RetrievalService()
    service.add_document("doc-lease-1", sample_chunks)

    res_empty = service.retrieve("doc-lease-1", "")
    assert res_empty.evidence_sufficient is False
    assert res_empty.evidence == []

    res_spaces = service.retrieve("doc-lease-1", "   \t\n ")
    assert res_spaces.evidence_sufficient is False
    assert res_spaces.evidence == []


def test_pluggable_fake_searcher_and_configurable_min_score(
    sample_chunks: list[DocumentChunk],
) -> None:
    """Demonstrate ChunkSearcher protocol pluggability and configurable MIN_SCORE."""
    class FakeScorer:
        def __init__(self, chunks: list[DocumentChunk]) -> None:
            self.chunks = chunks

        def search(
            self, query: str, top_k: int = 5
        ) -> list[tuple[DocumentChunk, float]]:
            # Assign fixed custom score of 10.0 to all chunks
            return [(c, 10.0) for c in self.chunks[:top_k]]

    # Case 1: MIN_SCORE=5.0 -> score 10.0 > 5.0 -> sufficient
    service_pass = RetrievalService(searcher_factory=FakeScorer, min_score=5.0)
    service_pass.add_document("doc-fake", sample_chunks)
    res_pass = service_pass.retrieve("doc-fake", "any query")
    assert res_pass.evidence_sufficient is True
    assert len(res_pass.evidence) >= 1

    # Case 2: MIN_SCORE=15.0 -> score 10.0 <= 15.0 -> insufficient
    service_fail = RetrievalService(searcher_factory=FakeScorer, min_score=15.0)
    service_fail.add_document("doc-fake", sample_chunks)
    res_fail = service_fail.retrieve("doc-fake", "any query")
    assert res_fail.evidence_sufficient is False


def test_no_document_text_or_question_in_logging(
    caplog: pytest.LogCaptureFixture,
    sample_chunks: list[DocumentChunk],
) -> None:
    caplog.set_level(logging.DEBUG)
    service = RetrievalService()

    service.add_document("doc-lease-1", sample_chunks)
    service.retrieve("doc-lease-1", "What is the security deposit amount?")
    service.delete_document("doc-lease-1")

    # Check all logged records
    for record in caplog.records:
        msg = record.getMessage()
        # Verify no document body text is logged
        assert "FAKE, illustrative only" not in msg
        assert "security deposit" not in msg
        assert "notice period" not in msg
        # Verify reason codes are used
        assert record.levelname in ("INFO", "WARNING", "ERROR")


# --- End-to-End Pipeline Test ---

def test_end_to_end_ingest_retrieve_and_agent_pipeline() -> None:
    """Full chain test: ingest_document -> RetrievalService -> run_agent with MockRuntime."""
    raw_document_text = (
        "14. Termination of Agreement\n"
        "The tenant may terminate this lease agreement upon giving thirty days written notice.\n"
        "15. Security Deposit\n"
        "A security deposit of one thousand dollars shall be retained by the landlord.\n"
    ).encode("utf-8")

    # Step 1: Ingest document
    ingest_res = ingest_document(
        document_id="doc-e2e-pipeline",
        filename="lease.txt",
        data=raw_document_text,
        source_type="contract",
    )
    assert ingest_res.status == "ready"
    assert ingest_res.reason_code == "OK"
    assert len(ingest_res.chunks) >= 2

    # Step 2: Index in RetrievalService
    service = RetrievalService()
    service.add_document("doc-e2e-pipeline", ingest_res.chunks)

    # Step 3: Retrieve evidence passages for question
    question = "What is the notice period for terminating the lease?"
    ret_res = service.retrieve("doc-e2e-pipeline", question)

    assert ret_res.evidence_sufficient is True
    assert len(ret_res.evidence) >= 1
    # Top evidence should be termination clause
    assert "14" in (ret_res.evidence[0].section or "")

    # Step 4: Run agent with MockRuntime("good") on the retrieved evidence
    agent_request = AgentRequest(
        document_id=ret_res.document_id,
        question=ret_res.question,
        evidence=ret_res.evidence,
        evidence_sufficient=ret_res.evidence_sufficient,
    )
    agent_response = run_agent(agent_request, MockRuntime("good"))

    # Assert final response is answered with verified citations
    assert agent_response.status == "answered"
    assert len(agent_response.findings) >= 1
    assert all(c.verified for f in agent_response.findings for c in f.evidence)
    assert agent_response.evidence_sufficient is True
