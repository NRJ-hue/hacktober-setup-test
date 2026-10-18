"""Local Ollama runtime for Gemma models with strict loopback security."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from backend.app.agent.runtime import LLMRuntime, RuntimeUnavailable

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemma4:e2b"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_TEMPERATURE = 0.0
DEFAULT_NUM_CTX = 4096

ALLOWED_LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})


def _validate_base_url(base_url: str) -> str:
    """Validate that base_url is strictly loopback HTTP.

    Raises ValueError if scheme is not http, if userinfo/credentials exist,
    or if host is not exactly 127.0.0.1, localhost, or ::1.
    """
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url must be a non-empty string")

    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "http":
        raise ValueError(f"Invalid scheme '{parsed.scheme}': only http is allowed")

    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise ValueError("Credentials or userinfo not allowed in base_url")

    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(
            f"Host '{hostname}' not allowed: only loopback (127.0.0.1, localhost, ::1) is permitted"
        )

    return f"http://{parsed.netloc}".rstrip("/")


class OllamaRuntime(LLMRuntime):
    """Local Ollama runtime communicating over localhost HTTP without proxies."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        temperature: float = DEFAULT_TEMPERATURE,
        num_ctx: int = DEFAULT_NUM_CTX,
    ) -> None:
        raw_model = model if model is not None else os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        raw_base_url = (
            base_url if base_url is not None else os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        )

        self.model = raw_model
        self.base_url = _validate_base_url(raw_base_url)
        self.timeout_s = float(timeout_s)
        self.temperature = float(temperature)
        self.num_ctx = int(num_ctx)
        self.call_count = 0

        # Enforce no-proxy opener so traffic cannot be redirected through external proxies
        self.proxy_handler = urllib.request.ProxyHandler({})
        self.opener = urllib.request.build_opener(self.proxy_handler)

    def generate(self, system: str, user: str) -> str:
        """Send chat request to Ollama /api/chat and return message content.

        Raises RuntimeUnavailable with a reason code only on any failure.
        Never logs or leaks prompt or response text.
        """
        self.call_count += 1
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.opener.open(req, timeout=self.timeout_s) as resp:
                resp_bytes = resp.read()

        except urllib.error.HTTPError as e:
            logger.warning("OLLAMA_HTTP_ERROR")
            if e.code == 404:
                raise RuntimeUnavailable("MODEL_NOT_FOUND_OR_404")
            raise RuntimeUnavailable(f"HTTP_{e.code}")

        except (urllib.error.URLError, TimeoutError) as e:
            logger.warning("OLLAMA_CONNECTION_ERROR")
            reason_str = str(getattr(e, "reason", e)).lower()
            if "timed out" in reason_str or isinstance(getattr(e, "reason", None), TimeoutError):
                raise RuntimeUnavailable("CONNECTION_TIMEOUT")
            raise RuntimeUnavailable("CONNECTION_FAILED")

        except Exception:
            logger.warning("OLLAMA_REQUEST_EXCEPTION")
            raise RuntimeUnavailable("RUNTIME_CONNECTION_FAILED")

        try:
            data = json.loads(resp_bytes.decode("utf-8"))
        except Exception:
            logger.warning("OLLAMA_MALFORMED_JSON")
            raise RuntimeUnavailable("MALFORMED_JSON_RESPONSE")

        if not isinstance(data, dict):
            logger.warning("OLLAMA_MALFORMED_RESPONSE_SHAPE")
            raise RuntimeUnavailable("MALFORMED_RESPONSE")

        message = data.get("message")
        if not isinstance(message, dict) or "content" not in message:
            logger.warning("OLLAMA_MISSING_MESSAGE_CONTENT")
            raise RuntimeUnavailable("MALFORMED_RESPONSE")

        content = message["content"]
        if not isinstance(content, str):
            logger.warning("OLLAMA_CONTENT_NOT_STRING")
            raise RuntimeUnavailable("MALFORMED_RESPONSE")

        return content

    def is_available(self) -> bool:
        """Check if Ollama server is answering and configured model is listed. Never raises."""
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with self.opener.open(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if not isinstance(data, dict):
                return False

            models = data.get("models", [])
            target = self.model.lower()
            for m in models:
                if isinstance(m, dict):
                    name = str(m.get("name", "")).lower()
                    model_id = str(m.get("model", "")).lower()
                    if name == target or model_id == target:
                        return True
                    if name.split(":")[0] == target.split(":")[0] and (":" not in target or name == target):
                        return True
            return False
        except Exception:
            return False
