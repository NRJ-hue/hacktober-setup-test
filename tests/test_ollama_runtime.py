"""Tests for local Ollama runtime security, payload formation, error mapping, and integration."""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
import pytest

from backend.app.agent.ollama_runtime import OllamaRuntime
from backend.app.agent.runtime import MockRuntime, RuntimeUnavailable
from backend.app.agent.workflow import get_runtime, run_agent
from backend.app.models.schemas import AgentRequest, AgentResponse, EvidencePassage


class _MockResponse:
    """Mock context manager for urllib responses."""

    def __init__(self, data: bytes, code: int = 200) -> None:
        self._data = data
        self.code = code

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _MockResponse:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


# --- Security & Base URL Tests ---

def test_base_url_loopback_allowed() -> None:
    r1 = OllamaRuntime(base_url="http://127.0.0.1:11434")
    assert r1.base_url == "http://127.0.0.1:11434"

    r2 = OllamaRuntime(base_url="http://localhost:11434")
    assert r2.base_url == "http://localhost:11434"

    r3 = OllamaRuntime(base_url="http://[::1]:11434")
    assert r3.base_url == "http://[::1]:11434"


def test_base_url_non_loopback_rejected() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        OllamaRuntime(base_url="http://example.com")

    with pytest.raises(ValueError, match="not allowed"):
        OllamaRuntime(base_url="http://192.168.1.5:11434")

    with pytest.raises(ValueError, match="Credentials or userinfo"):
        OllamaRuntime(base_url="http://127.0.0.1@evil.com")


def test_base_url_https_and_other_schemes_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid scheme"):
        OllamaRuntime(base_url="https://127.0.0.1:11434")

    with pytest.raises(ValueError, match="Invalid scheme"):
        OllamaRuntime(base_url="ftp://127.0.0.1:11434")


def test_proxy_handler_is_empty() -> None:
    runtime = OllamaRuntime()
    # Check that ProxyHandler in opener is empty ({})
    assert isinstance(runtime.proxy_handler, urllib.request.ProxyHandler)
    assert runtime.proxy_handler.proxies == {}


# --- Payload Formation Tests ---

def test_generate_payload_formation(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: list[urllib.request.Request] = []

    def mock_open(req: urllib.request.Request, timeout: float = 120.0):
        captured_request.append(req)
        resp_payload = {
            "message": {
                "role": "assistant",
                "content": '{"answer": "OK", "findings": []}',
            }
        }
        return _MockResponse(json.dumps(resp_payload).encode("utf-8"))

    runtime = OllamaRuntime(
        model="gemma4:e2b",
        temperature=0.0,
        num_ctx=4096,
    )
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    content = runtime.generate("SYSTEM_INSTRUCTIONS", "USER_PROMPT")

    assert content == '{"answer": "OK", "findings": []}'
    assert len(captured_request) == 1

    req = captured_request[0]
    assert req.full_url == "http://127.0.0.1:11434/api/chat"
    assert req.get_method() == "POST"
    assert req.headers["Content-type"] == "application/json"

    sent_data = json.loads(req.data.decode("utf-8"))
    assert sent_data["model"] == "gemma4:e2b"
    assert sent_data["stream"] is False
    assert sent_data["format"] == "json"
    assert sent_data["options"]["temperature"] == 0.0
    assert sent_data["options"]["num_ctx"] == 4096
    assert sent_data["messages"] == [
        {"role": "system", "content": "SYSTEM_INSTRUCTIONS"},
        {"role": "user", "content": "USER_PROMPT"},
    ]


# --- Error Mapping & Prompt Confidentiality Tests ---

def test_timeout_raises_runtime_unavailable_no_prompt_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_open(req: urllib.request.Request, timeout: float = 120.0):
        raise urllib.error.URLError(reason=TimeoutError("Connection timed out"))

    runtime = OllamaRuntime()
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    secret_sys = "CONFIDENTIAL_SYSTEM_RULES"
    secret_usr = "CONFIDENTIAL_USER_QUERY"

    with pytest.raises(RuntimeUnavailable) as exc_info:
        runtime.generate(secret_sys, secret_usr)

    assert exc_info.value.reason == "CONNECTION_TIMEOUT"
    assert secret_sys not in str(exc_info.value)
    assert secret_usr not in str(exc_info.value)


def test_http_404_raises_runtime_unavailable_no_prompt_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_open(req: urllib.request.Request, timeout: float = 120.0):
        raise urllib.error.HTTPError(
            url="http://127.0.0.1:11434/api/chat",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b'{"error": "model not found"}'),
        )

    runtime = OllamaRuntime()
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    secret_sys = "SECRET_SYSTEM_TEXT"
    secret_usr = "SECRET_USER_TEXT"

    with pytest.raises(RuntimeUnavailable) as exc_info:
        runtime.generate(secret_sys, secret_usr)

    assert exc_info.value.reason == "MODEL_NOT_FOUND_OR_404"
    assert secret_sys not in str(exc_info.value)
    assert secret_usr not in str(exc_info.value)


def test_malformed_json_raises_runtime_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_open(req: urllib.request.Request, timeout: float = 120.0):
        return _MockResponse(b"this is not valid json")

    runtime = OllamaRuntime()
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    secret_sys = "CONFIDENTIAL_SYSTEM_PROMPT"
    secret_usr = "CONFIDENTIAL_USER_PROMPT"

    with pytest.raises(RuntimeUnavailable) as exc_info:
        runtime.generate(secret_sys, secret_usr)

    assert exc_info.value.reason == "MALFORMED_JSON_RESPONSE"
    assert secret_sys not in str(exc_info.value)
    assert secret_usr not in str(exc_info.value)


def test_malformed_structure_raises_runtime_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_open(req: urllib.request.Request, timeout: float = 120.0):
        # Missing 'message' or 'content'
        return _MockResponse(b'{"unexpected_key": 123}')

    runtime = OllamaRuntime()
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    with pytest.raises(RuntimeUnavailable) as exc_info:
        runtime.generate("system", "user")

    assert exc_info.value.reason == "MALFORMED_RESPONSE"


# --- is_available() Tests ---

def test_is_available_true_when_model_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_open(req: urllib.request.Request, timeout: float = 5.0):
        tags = {"models": [{"name": "gemma4:e2b"}, {"name": "llama3:8b"}]}
        return _MockResponse(json.dumps(tags).encode("utf-8"))

    runtime = OllamaRuntime(model="gemma4:e2b")
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    assert runtime.is_available() is True


def test_is_available_false_when_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_open(req: urllib.request.Request, timeout: float = 5.0):
        tags = {"models": [{"name": "mistral:7b"}]}
        return _MockResponse(json.dumps(tags).encode("utf-8"))

    runtime = OllamaRuntime(model="gemma4:e2b")
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    assert runtime.is_available() is False


def test_is_available_false_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_open(req: urllib.request.Request, timeout: float = 5.0):
        raise urllib.error.URLError("Server unreachable")

    runtime = OllamaRuntime()
    monkeypatch.setattr(runtime.opener, "open", mock_open)

    # Must never raise
    assert runtime.is_available() is False


# --- Factory & Workflow Configuration Tests ---

def test_get_runtime_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEGAL_AGENT_RUNTIME", "mock")
    r_mock = get_runtime()
    assert isinstance(r_mock, MockRuntime)

    monkeypatch.setenv("LEGAL_AGENT_RUNTIME", "ollama")
    r_ollama = get_runtime()
    assert isinstance(r_ollama, OllamaRuntime)


# --- Integration Test (Marked ollama) ---

@pytest.mark.ollama
def test_ollama_runtime_live_integration() -> None:
    runtime = OllamaRuntime()
    if not runtime.is_available():
        pytest.skip("Ollama server or configured model is unavailable locally")

    p = EvidencePassage(
        source_id="live-p1-c0",
        source_type="contract",
        page=1,
        section="14. Termination",
        text="The tenant may terminate this lease upon giving thirty days written notice.",
    )
    req = AgentRequest(
        document_id="doc-live-test",
        question="What is the notice period for terminating the lease?",
        evidence=[p],
        evidence_sufficient=True,
    )

    res = run_agent(req, runtime=runtime)
    assert isinstance(res, AgentResponse)
