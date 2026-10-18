"""Retrieval sufficiency evaluation on a synthetic 30-page contract document."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ingestion.service import ingest_document
from backend.app.retrieval.service import RetrievalService


def main() -> None:
    # Build 30 pages of realistic contractual text
    pages = []
    topics = [
        "Definitions and Interpretations",
        "Scope of Engagement and Services",
        "Compensation and Payment Terms",
        "Invoicing and Taxes",
        "Term of Agreement",
        "Termination for Cause",
        "Termination for Convenience",
        "Confidentiality Obligations",
        "Non-Disclosure Covenants",
        "Intellectual Property Ownership",
        "Work Product and Inventions",
        "Representations and Warranties",
        "Disclaimers of Warranties",
        "Limitation of Liability",
        "Indemnification Obligations",
        "Insurance Requirements",
        "Independent Contractor Status",
        "Non-Solicitation of Personnel",
        "Governing Law and Jurisdiction",
        "Dispute Resolution and Arbitration",
        "Force Majeure Events",
        "Notices and Communications",
        "Severability of Provisions",
        "Entire Agreement and Merger",
        "Amendments and Modifications",
        "Waiver of Rights",
        "Assignment and Delegation",
        "Successors and Assigns",
        "Counterparts and Electronic Signatures",
        "Export Compliance and Sanctions",
    ]

    for idx, topic in enumerate(topics, start=1):
        page_text = (
            f"=== Page {idx} ===\n"
            f"Section {idx}. {topic}.\n"
            f"The parties hereto agree with respect to {topic.lower()} that all duties, "
            f"covenants, and statutory obligations shall be strictly fulfilled according to the terms herein. "
            f"Neither party shall evade responsibilities outlined under Section {idx} during the term.\n"
        )
        if topic == "Dispute Resolution and Arbitration":
            page_text += (
                "Any dispute arising out of or relating to this contract shall be settled by binding "
                "arbitration administered by the American Arbitration Association under its Commercial "
                "Arbitration Rules in Wilmington, Delaware.\n"
            )
        pages.append(page_text)

    full_doc = "\n\n".join(pages)
    doc_bytes = full_doc.encode("utf-8")

    doc_id = "doc-30-page"
    ingest_res = ingest_document(doc_id, "contract_30_pages.txt", doc_bytes)
    chunks = ingest_res.chunks
    print(f"Ingested 30-page document: {len(chunks)} chunks produced across {len(pages)} pages.")

    retrieval_svc = RetrievalService(min_score=0.5)
    retrieval_svc.add_document(doc_id, chunks)

    test_queries = [
        ("What are the rules for binding arbitration and dispute resolution?", True, "Targeted topic present"),
        ("What insurance coverage is required?", True, "Topic present in Section 16"),
        ("What are the definitions and interpretations?", True, "Topic present in Section 1"),
        ("Are pets or dogs allowed on the premises?", False, "Document silent (not in contract)"),
        ("What is the speed of light in a vacuum?", False, "Completely off-topic / zero term overlap"),
        ("What is the penalty for late parking?", False, "Document silent"),
    ]

    print("\n--- 30-PAGE RETRIEVAL SUFFICIENCY TESTS ---")
    for q, expected_sufficient, description in test_queries:
        res = retrieval_svc.retrieve(doc_id, q)
        # Search directly for top score
        searcher = retrieval_svc._searchers[doc_id]
        scored = searcher.search(q, top_k=1)
        top_score = scored[0][1] if scored else 0.0

        status = "PASS" if res.evidence_sufficient == expected_sufficient else "FAIL"
        print(
            f"Query: '{q[:40]}...' | "
            f"Top Score: {top_score:.3f} | "
            f"Sufficient: {res.evidence_sufficient} (expected {expected_sufficient}) | "
            f"Result: {status} ({description})"
        )


if __name__ == "__main__":
    main()
