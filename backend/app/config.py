"""Application configuration and environment settings."""
from __future__ import annotations

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Configuration settings loaded from environment variables with defaults."""

    max_upload_bytes: int = Field(default=10_000_000)
    max_question_chars: int = Field(default=1000)
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @classmethod
    def load(cls) -> Settings:
        raw_max_upload = os.getenv("MAX_UPLOAD_BYTES")
        max_upload = int(raw_max_upload) if raw_max_upload is not None else 10_000_000

        raw_max_q = os.getenv("MAX_QUESTION_CHARS")
        max_q = int(raw_max_q) if raw_max_q is not None else 1000

        raw_origins = os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
        origins = [orig.strip() for orig in raw_origins.split(",") if orig.strip()]

        return cls(
            max_upload_bytes=max_upload,
            max_question_chars=max_q,
            allowed_origins=origins,
        )


settings = Settings.load()
