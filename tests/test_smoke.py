"""Smoke tests — verify the project skeleton is importable and FastAPI works."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_import_backend_app() -> None:
    """Importing backend.app should succeed without errors."""
    import backend.app  # noqa: F401


def test_ping_returns_200() -> None:
    """A minimal FastAPI app should respond 200 on /ping."""
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
