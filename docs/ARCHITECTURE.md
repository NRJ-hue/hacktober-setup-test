# Architecture

The Private Legal Document Triage Agent is a privacy-first, on-device legal assistance system designed for local execution. All document processing, indexing, and generative reasoning occur strictly on the user's host machine.

## High-Level Pipeline

```
[User Document: PDF / TXT]
       │
       ▼
[Ingestion & Validation] (Type & size verification, PDF/TXT parsing, OCR detection)
       │
       ▼
[Normalization & Chunking] (Structure detection, clause-aware chunking, source tagging)
       │
       ▼
[In-Memory BM25 Index] (Lexical indexing via pluggable ChunkSearcher, sufficiency scoring)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[User Question] ──▶ [Retrieval Service] ──▶ [Evidence Assembly]
                                                  │
                                                  ▼
                                      [Agent Workflow Orchestrator]
                                                  │
                   ┌──────────────────────────────┼──────────────────────────────┐
                   ▼                              ▼                              ▼
          [System Prompting]            [Ollama Runtime]               [JSON Parser / Retry]
          - Role & restrictions        - Loopback HTTP only           - Schema validation
          - Anti-injection markers      - Strict proxy suppression     - Single-retry on error
                   │                              │                              │
                   └──────────────────────────────┼──────────────────────────────┘
                                                  ▼
                                     [Citation Validator]
                                     - Fuzzy substring quote verification
                                     - Character-level precision checks
                                     - Metadata backfill (source, page, section)
                                                  │
                                                  ▼
                                     [Response Guardrails]
                                     - Legal verdict refusal (enforceability, legality)
                                     - Paraphrase & injection defense
                                     - Definitive language hedging
                                     - Escalation & disclaimer enforcement
                                                  │
                                                  ▼
                                  [FastAPI & React UI Presentation]
```

## Modules

### 1. Ingestion (`backend/app/ingestion` & `backend/app/document`)
- **`validator.py`**: Enforces strict extension and magic byte verification (`%PDF-` header for PDF, valid UTF-8 without NUL bytes for TXT). Rejects files exceeding configured size limits.
- **`pdf_parser.py`**: Extracts text page-by-page using `pypdf`, flagging scanned image-only PDFs with an `OCR_REQUIRED` error code.
- **`txt_parser.py`**: Extracts plain text, detecting page delimiters (`=== Page N ===` or form-feed `\f`).
- **`normalizer.py`**: Normalizes whitespace, replaces non-standard Unicode hyphens/quotes, and cleans search strings.
- **`section_detector.py`**: Identifies contract section headings (`Section 1.`, `Clause 2.`, `Article III.`, etc.).
- **`chunker.py`**: Splits document pages into clause-aware chunks with source-type tags and location metadata.
- **`service.py`**: High-level ingestion coordinator returning structured `IngestResult` without logging document text.

### 2. Lexical Retrieval (`backend/app/retrieval`)
- **`base.py`**: Defines the `ChunkSearcher` Protocol (`search(query, top_k) -> list[tuple[DocumentChunk, float]]`).
- **`bm25.py`**: In-memory BM25 index implementation using normalized tokenization.
- **`service.py`**: `RetrievalService` indexes document chunks and retrieves top-$k$ evidence passages. Determines evidence sufficiency using a configurable minimum threshold (`MIN_SCORE = 0.5`).

### 3. Agent & Runtime (`backend/app/agent`)
- **`prompts.py`**: Compact legal triage system prompt emphasizing untrusted evidence, exact quotation, abstention when silent, and disclaimers.
- **`runtime.py`**: Abstract `LLMRuntime` interface, robust JSON parser with Markdown fence extraction, and deterministic `MockRuntime`.
- **`ollama_runtime.py`**: HTTP client for local Ollama running `gemma4:e2b`. Enforces loopback-only URLs (`127.0.0.1`, `localhost`, `::1`) and disables HTTP proxies.
- **`workflow.py`**: `run_agent()` orchestrates retrieval sufficiency gating, prompt construction, model execution, parser retries, citation backfilling, suspicious chunk filtering, and response guard enforcement.

### 4. Safety & Verification (`backend/app/safety`)
- **`citation_validator.py`**: Computes character-level fuzzy substring matching (`ratio >= 0.85`) between quotes and retrieved source passages. Unverified citations are flagged or backfilled.
- **`response_guard.py`**: Classifies question intent (`legal_verdict`, `outside_document`, `normal`). Replaces legal verdicts with mandatory refusals, hedges definitive assertions, flags prompt injection markers, and sets escalation flags.

### 5. Storage & API (`backend/app/storage` & `backend/app/api`)
- **`session_store.py`**: In-memory store holding transient session state (`document_id`, page/chunk counts, processing status). Raw document bytes are discarded immediately upon ingestion.
- **`main.py`**, **`documents.py`**, **`questions.py`**: FastAPI endpoints serving REST APIs under `/api`.

### 6. User Interface (`frontend/src`)
- Privacy-preserving React + TypeScript + Vite single-page application.
- Direct communication with `http://127.0.0.1:8000/api`.
- Plain text DOM rendering (no markdown execution or HTML evaluation).
- Screen-reader accessible live regions (`aria-live="polite"`).

## Source-Type Separation
The pipeline explicitly tracks `SourceType`:
- `"contract"`: Commercial agreements, residential leases, vendor contracts.
- `"legislation"`: Statutes, regulations, and legislative enactments.
- `"judgment"`: Judicial rulings, case law opinions.

Citations and findings maintain strict provenance throughout retrieval, validation, and presentation, preventing cross-source contamination.
