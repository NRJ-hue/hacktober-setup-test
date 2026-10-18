"""Socket-level privacy verification script.

Monkeypatches socket.socket.connect to track all outbound connection attempts
during a complete document ingest -> retrieve -> run_agent execution cycle.
Fails if any destination other than 127.0.0.1:11434 (local Ollama) is accessed.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
ALLOWED_PORT = 11434


def main() -> None:
    recorded_destinations: list[tuple[str, int]] = []
    disallowed_destinations: list[tuple[str, int]] = []

    orig_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: tuple | str) -> None:
        if isinstance(address, tuple) and len(address) >= 2:
            host, port = address[0], address[1]
            recorded_destinations.append((str(host), int(port)))
            if str(host) not in ALLOWED_HOSTS or int(port) != ALLOWED_PORT:
                disallowed_destinations.append((str(host), int(port)))
        return orig_connect(self, address)

    socket.socket.connect = guarded_connect  # type: ignore[assignment]

    try:
        from backend.app.agent.ollama_runtime import OllamaRuntime
        from backend.app.agent.workflow import run_agent
        from backend.app.ingestion.service import ingest_document
        from backend.app.models.schemas import AgentRequest
        from backend.app.retrieval.service import RetrievalService

        # 1. Ingestion (pure local CPU)
        doc_id = "privacy-doc-01"
        doc_bytes = (
            b"1. Rent. Tenant agrees to pay rent of $1,000 per month on the first day.\n"
            b"2. Deposit. Deposit of $1,000 shall be held in escrow."
        )
        ingest_res = ingest_document(doc_id, "privacy_test.txt", doc_bytes)
        chunks = ingest_res.chunks

        # 2. Retrieval (pure local in-memory BM25)
        retrieval_svc = RetrievalService()
        doc_id = "privacy-doc-01"
        retrieval_svc.add_document(doc_id, chunks)
        ret_result = retrieval_svc.retrieve(doc_id, "What is the rent?")

        # 3. Agent workflow (Ollama local runtime)
        runtime = OllamaRuntime()
        if not runtime.is_available():
            print("ERROR: Ollama server is not reachable at 127.0.0.1:11434.")
            sys.exit(1)

        req = AgentRequest(
            document_id=doc_id,
            question=ret_result.question,
            evidence=ret_result.evidence,
            evidence_sufficient=ret_result.evidence_sufficient,
        )

        _ = run_agent(req, runtime=runtime)

    finally:
        socket.socket.connect = orig_connect  # type: ignore[assignment]

    print("=== PRIVACY SOCKET AUDIT REPORT ===")
    print(f"Total socket connect calls: {len(recorded_destinations)}")
    print("Unique recorded destinations:")
    unique_dests = sorted(set(recorded_destinations))
    for dest_host, dest_port in unique_dests:
        status = (
            "ALLOWED (Local Ollama)"
            if (dest_host in ALLOWED_HOSTS and dest_port == ALLOWED_PORT)
            else "FORBIDDEN (External Leak)"
        )
        print(f"  - {dest_host}:{dest_port} -> {status}")

    if disallowed_destinations:
        print(f"\nAUDIT FAILED: Disallowed connections detected: {disallowed_destinations}")
        sys.exit(1)

    print("\nAUDIT PASSED: 100% of outbound connections were to localhost Ollama (127.0.0.1:11434).")
    print("No external, cloud, telemetry, or third-party connections occurred.")


if __name__ == "__main__":
    main()
