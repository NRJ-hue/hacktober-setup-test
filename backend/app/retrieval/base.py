"""Base protocols and types for retrieval searchers."""
from __future__ import annotations

from typing import Protocol
from backend.app.models.schemas import DocumentChunk


class ChunkSearcher(Protocol):
    """Protocol for chunk-level document search backends."""

    def search(
        self, query: str, top_k: int = 5
    ) -> list[tuple[DocumentChunk, float]]:
        """Search indexed chunks for a query and return scored results."""
        ...
