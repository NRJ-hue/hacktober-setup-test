# Privacy & Security Architecture

The Private Legal Document Triage Agent is engineered with strict zero-egress privacy principles. All computations, from text parsing to LLM inference, occur on the local device.

## Threat Model

1. **Third-Party Data Exfiltration**:
   - *Risk*: Confidential contract clauses, trade secrets, or client data leaked to external cloud inference APIs, telemetry collectors, or third-party loggers.
   - *Mitigation*: Hardened loopback networking, proxy suppression, zero external dependencies.

2. **Unintentional Disk Persistence**:
   - *Risk*: Sensitive uploads left in temporary directories, logs, or persistent vector databases.
   - *Mitigation*: Ephemeral in-memory structures only; immediate deletion of uploaded bytes; zero database files created on disk.

3. **Prompt Injection & Overrides**:
   - *Risk*: Adversarial contract text attempting to override triage rules, fabricate findings, or bypass legal disclaimers.
   - *Mitigation*: Evidence tagging with `<evidence>` envelopes, regex injection scanning, untrusted data segregation, and suspicious citation discarding.

## Tested Guarantees vs. Assumptions

### Tested Guarantees
- **Socket-Level Loopback Assertion**: Tested via [privacy_check.py](file:///c:/Users/nilab/hacktober-setup-test/scripts/privacy_check.py). A monkeypatched socket guard confirms that 100% of outbound network calls during ingestion, indexing, retrieval, and inference connect exclusively to `127.0.0.1:11434`.
- **Zero Disk Writes**: Tested via [test_temp_files.py](file:///c:/Users/nilab/hacktober-setup-test/scripts/test_temp_files.py). Uploading and indexing documents produces 0 new files on disk in the repository or the OS temporary folder (`tempfile.gettempdir()`).
- **No Telemetry / No CDNs**: Grep audit of all repository source code confirms no tracking scripts, analytics, or external font/library URLs. The frontend communicates exclusively with `http://127.0.0.1:8000/api`.
- **Data-Leak-Free Logging**: All application logging outputs only reason codes and metadata counts. Document text, quotes, user queries, and raw model prompts are never emitted to stdout or log files.

### Assumptions & External Boundaries
- **Model Distribution**: Model acquisition (`ollama pull gemma4:e2b`) requires an initial network download from Ollama's registry. Once pulled, no further connection is needed.
- **Operating System Isolation**: The system assumes the host operating system and local Ollama daemon are untampered and secure.

## Complete Inventory of Network Endpoints

| Component | Target URL | Protocol | Direction | Purpose |
|---|---|---|---|---|
| Setup (Once) | `registry.ollama.ai` | HTTPS | Egress | Downloading `gemma4:e2b` weights |
| `OllamaRuntime` | `http://127.0.0.1:11434/api/tags` | HTTP | Loopback | Checking model availability |
| `OllamaRuntime` | `http://127.0.0.1:11434/api/chat` | HTTP | Loopback | Generating structured responses |
| Frontend | `http://127.0.0.1:8000/api/*` | HTTP | Loopback | Uploading documents & asking questions |

*Note: All runtime connections are strictly loopback (`127.0.0.1`). Any request to an external IP or domain is rejected with a `ValueError`.*

## Manual Offline Reproduction Procedure

To verify offline independence manually:

1. Disconnect your machine from the internet (turn off Wi-Fi and unplug Ethernet).
2. Start the local Ollama daemon:
   ```bash
   ollama serve
   ```
3. Start the FastAPI backend:
   ```bash
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
4. Start the frontend:
   ```bash
   cd frontend && npm run dev
   ```
5. Open your browser to `http://localhost:5173`, upload a document (PDF/TXT), and submit a question.
6. Observe that the analysis completes normally with zero network access.
