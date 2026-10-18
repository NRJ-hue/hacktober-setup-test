"""Upload validation for legal documents."""
from __future__ import annotations

import logging
from typing import Literal
from pydantic import BaseModel

logger = logging.getLogger(__name__)

UploadKind = Literal["pdf", "txt"]


class ValidationResult(BaseModel):
    """Result of file upload validation."""

    ok: bool
    kind: UploadKind | None = None
    reason_code: str


def validate_upload(
    filename: str,
    data: bytes,
    max_bytes: int = 10_000_000,
) -> ValidationResult:
    """Validate uploaded document file size, extension, and content signature.

    Never trusts filename alone. Checks real byte content.
    Logs reason codes only; never logs document content or filenames.
    """
    if not data or len(data) == 0:
        logger.warning("UPLOAD_VALIDATION_EMPTY_FILE")
        return ValidationResult(ok=False, kind=None, reason_code="EMPTY_FILE")

    if len(data) > max_bytes:
        logger.warning("UPLOAD_VALIDATION_FILE_TOO_LARGE")
        return ValidationResult(ok=False, kind=None, reason_code="FILE_TOO_LARGE")

    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        if not data.startswith(b"%PDF-"):
            logger.warning("UPLOAD_VALIDATION_CONTENT_TYPE_MISMATCH")
            return ValidationResult(
                ok=False, kind=None, reason_code="CONTENT_TYPE_MISMATCH"
            )
        logger.info("UPLOAD_VALIDATION_SUCCESS")
        return ValidationResult(ok=True, kind="pdf", reason_code="OK")

    if lower_name.endswith(".txt"):
        if b"\x00" in data:
            logger.warning("UPLOAD_VALIDATION_CONTAINS_NUL_BYTES")
            return ValidationResult(
                ok=False, kind=None, reason_code="CONTAINS_NUL_BYTES"
            )
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("UPLOAD_VALIDATION_INVALID_UTF8")
            return ValidationResult(
                ok=False, kind=None, reason_code="INVALID_UTF8"
            )
        logger.info("UPLOAD_VALIDATION_SUCCESS")
        return ValidationResult(ok=True, kind="txt", reason_code="OK")

    logger.warning("UPLOAD_VALIDATION_UNSUPPORTED_TYPE")
    return ValidationResult(ok=False, kind=None, reason_code="UNSUPPORTED_FILE_TYPE")
