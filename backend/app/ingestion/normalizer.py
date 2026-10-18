"""Text normalizer for search operations."""
from __future__ import annotations


def normalize_for_search(text: str) -> str:
    """Return a lowercased, whitespace-collapsed copy of text for search ONLY.

    CRITICAL: Original page text is never modified or replaced. This function
    is strictly used to generate derived query/lookup keys.
    """
    return " ".join(text.lower().split())
