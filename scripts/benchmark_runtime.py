"""Benchmark Ollama runtime performance on fixture questions.

Measures latency, response status, findings count, verified citation count,
retry occurrences, and peak Python memory usage without logging prompt or document text.
"""
from __future__ import annotations

import sys
import time
import tracemalloc
from pathlib import Path

# Ensure repository root is on sys.path for standalone script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.agent.ollama_runtime import OllamaRuntime
from backend.app.agent.workflow import run_agent
from backend.app.models.schemas import AgentRequest, EvidencePassage


def main() -> None:
    tracemalloc.start()
    runtime = OllamaRuntime()

    if not runtime.is_available():
        print(
            "OLLAMA_UNAVAILABLE: Server not answering or configured model missing. "
            "Please ensure Ollama is running and the model is pulled."
        )
        sys.exit(1)

    passages = [
        EvidencePassage(
            source_id="bench-p1-c0",
            source_type="contract",
            page=1,
            section="14. Termination",
            text="The tenant may terminate this lease upon giving thirty days written notice to the landlord.",
        ),
        EvidencePassage(
            source_id="bench-p1-c1",
            source_type="contract",
            page=1,
            section="15. Security Deposit",
            text="The security deposit of two thousand dollars shall be retained in an escrow account.",
        ),
        EvidencePassage(
            source_id="bench-p1-c2",
            source_type="contract",
            page=2,
            section="16. Late Payment",
            text="A late fee of fifty dollars applies if rent is not received by the fifth day of the month.",
        ),
        EvidencePassage(
            source_id="bench-p1-c3",
            source_type="contract",
            page=2,
            section="17. Subletting",
            text="Subletting the premises requires prior written consent from the landlord.",
        ),
        EvidencePassage(
            source_id="bench-p1-c4",
            source_type="contract",
            page=3,
            section="18. Maintenance",
            text="The landlord shall maintain the structural integrity and exterior walls of the property.",
        ),
    ]

    questions = [
        "What is the notice period for terminating the lease?",
        "What are the security deposit requirements?",
        "What is the late fee policy?",
        "Is subletting allowed without consent?",
        "What are the landlord maintenance obligations?",
    ]

    total_latency = 0.0
    total_findings = 0
    total_verified_citations = 0

    print("--- BENCHMARK RUN (OllamaRuntime) ---")
    for idx, q_text in enumerate(questions, start=1):
        req = AgentRequest(
            document_id="doc-benchmark",
            question=q_text,
            evidence=passages,
            evidence_sufficient=True,
        )

        prior_calls = runtime.call_count
        t0 = time.perf_counter()
        res = run_agent(req, runtime=runtime)
        t1 = time.perf_counter()

        latency = t1 - t0
        total_latency += latency
        findings_count = len(res.findings)
        total_findings += findings_count

        verified_citations = sum(
            len([c for c in f.evidence if c.verified]) for f in res.findings
        )
        total_verified_citations += verified_citations
        retried = (runtime.call_count - prior_calls) > 1

        print(
            f"Q{idx}: latency={latency:.2f}s, status={res.status}, "
            f"findings={findings_count}, verified_citations={verified_citations}, retry={retried}"
        )

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_bytes / (1024 * 1024)

    print("--- TOTALS ---")
    print(f"Total Latency: {total_latency:.2f}s (Average: {total_latency / len(questions):.2f}s)")
    print(f"Total Findings: {total_findings}")
    print(f"Total Verified Citations: {total_verified_citations}")
    print(f"Python Peak Memory: {peak_mb:.2f} MB")
    print("Note: Ollama's own memory footprint is external to Python and must be inspected via OS task manager.")


if __name__ == "__main__":
    main()
