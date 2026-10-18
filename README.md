# Private Legal Document Triage Agent

A privacy-first, fully on-device agent for triaging legal documents. All document ingestion, chunking, lexical indexing, and model inference occur strictly on the user's host machine. No document text, user queries, or model outputs ever leave the machine.

## Scope & Applicability

- **Document Types**: English-language contracts, residential leases, and employment agreements.
- **File Formats**: Clean UTF-8 plain text (`.txt`) and digital vector PDFs (`.pdf`).
- **Out of Scope**: Scanned image PDFs requiring OCR (`OCR_REQUIRED` error is raised), non-English documents, and automated generation of binding legal advice.
- **Legal Disclaimer**: *Preliminary document understanding only, not legal advice. Always consult a qualified legal professional for binding legal determinations.*

## Main Technical Contribution

A completely on-device, verifiable legal document triage pipeline that couples:
1. **Clause-Aware Chunking & Lexical Indexing**: Tokenized BM25 search over structured document clauses with an explicit sufficiency threshold (`MIN_SCORE = 0.5`) to prevent hallucinations on unaddressed topics.
2. **Deterministic Citation Verification**: Fuzzy character-level substring matching (`ratio >= 0.85`) ensuring every finding quotes verifiable source text.
3. **Multi-Tier Safety Guardrails**: Hardened prompt boundary envelopes (`<evidence>` tags), regex-based question intent classification, mandatory refusal of legal verdicts (e.g. enforceability), and definitive language hedging.
4. **Zero-Egress Privacy Guarantees**: Enforced loopback communication (`127.0.0.1:11434` only), proxy suppression, and ephemeral in-memory storage with zero disk writes.

---

## Quickstart

### Prerequisites

- **Python 3.10+**
- **Node.js 18+ & npm**
- **Ollama** with `gemma4:e2b` (for local generative inference):
  ```bash
  ollama pull gemma4:e2b
  ```

### 1. Backend Setup

```bash
# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Running the Backend

#### Option A: Mock Mode (Fast testing without Ollama)
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

#### Option B: Real Model Mode (Ollama + Gemma 4 2B)
Ensure the Ollama service is running (`ollama serve`), then:
```bash
# Windows PowerShell:
$env:LEGAL_AGENT_RUNTIME="ollama"
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# macOS / Linux:
LEGAL_AGENT_RUNTIME=ollama uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup & Run

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## Verification & Auditing Scripts

The repository includes dedicated verification tools to audit functionality and privacy guarantees:

- **Run Standard Unit Test Suite** (173 tests, excludes live Ollama):
  ```bash
  python -m pytest -q -m "not ollama"
  ```

- **Run Live Ollama Integration Tests**:
  ```bash
  python -m pytest -q -m "ollama"
  ```

- **Run Socket-Level Privacy Audit**:
  ```bash
  python scripts/privacy_check.py
  ```
  *Monkeypatches socket connections to verify that 100% of outbound connections go strictly to `127.0.0.1:11434`.*

- **Run Disk Persistence Audit**:
  ```bash
  python scripts/test_temp_files.py
  ```
  *Asserts zero files are written to repository or temporary directories during uploads.*

- **Run 30-Page Retrieval Sufficiency Test**:
  ```bash
  python scripts/test_30page_retrieval.py
  ```
  *Validates BM25 scoring and sufficiency decisions across a 30-page contract.*

- **Run Comprehensive Model Evaluation**:
  ```bash
  python scripts/evaluate_agent.py
  ```
  *Evaluates the 8 core triage scenarios against a synthetic contract.*

---

## Troubleshooting

- **`OCR_REQUIRED` Upload Rejection**:
  - The document contains image-only or scanned pages without embedded text layers. Convert the document using an external OCR tool prior to upload.
- **Ollama Connection Refused (`RUNTIME_UNAVAILABLE`)**:
  - Verify that the Ollama service is actively running: `curl http://127.0.0.1:11434/api/tags`.
  - Ensure the model `gemma4:e2b` has been pulled: `ollama list`.
- **`FILE_TOO_LARGE`**:
  - Uploaded files exceed the 10 MB limit (`MAX_UPLOAD_BYTES`).
- **`PARSE_FAILURE_RETRY` in Logs**:
  - The small edge model returned non-standard formatting. The system automatically retries with a formatting reinforcement suffix. If parsing fails a second time, it safely abstains with `status="error"`.

---

## Documentation

Detailed architectural and empirical documentation is located in [`docs/`](file:///c:/Users/nilab/hacktober-setup-test/docs/):
- [`docs/ARCHITECTURE.md`](file:///c:/Users/nilab/hacktober-setup-test/docs/ARCHITECTURE.md): System components, data flow, and source-type tracking.
- [`docs/PRIVACY.md`](file:///c:/Users/nilab/hacktober-setup-test/docs/PRIVACY.md): Threat model, tested guarantees, and offline testing guide.
- [`docs/MODEL.md`](file:///c:/Users/nilab/hacktober-setup-test/docs/MODEL.md): Model specs, licensing, hardware profiling, and latency benchmarks.
- [`docs/EVALUATION.md`](file:///c:/Users/nilab/hacktober-setup-test/docs/EVALUATION.md): Full evaluation table and analysis of limitations.
- [`docs/DATASETS.md`](file:///c:/Users/nilab/hacktober-setup-test/docs/DATASETS.md): Synthetic test sets and optional CUAD evaluation.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](file:///c:/Users/nilab/hacktober-setup-test/LICENSE) for details.