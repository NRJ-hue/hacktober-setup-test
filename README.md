# Private Legal Document Triage Agent

A privacy-first, fully on-device agent for triaging legal documents. All
processing happens locally — no document text, user queries, or model inputs
ever leave the machine.

> **Work in progress.**

## Quickstart

```bash
# Create and activate the virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the test suite
python -m pytest -q

# Run the application backend
uvicorn backend.app.main:app --host 127.0.0.1
```

## Frontend

The frontend is a privacy-preserving React + TypeScript + Vite application.

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

> **Note:**
> - The backend must be running on `http://127.0.0.1:8000` (or set `VITE_API_BASE`).
> - By default, the backend runs with mock agent mode. To get real model answers, ensure Ollama is running and start the backend with `LEGAL_AGENT_RUNTIME=ollama`.