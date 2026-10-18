"""Section heading detection for legal documents."""
from __future__ import annotations

import re

_SECTION_PATTERN = re.compile(
    r"(?m)^\s*("
    r"(?:Section|Clause|Article|ARTICLE)\s+(?:[0-9]+(?:\.[0-9]+)*|[IVXLCDM]+)"
    r"|"
    r"(?:\d+(?:\.\d+)+|\d+\.)"
    r")(?=[\s\:\-\.]|$)",
)


def detect_sections(page_text: str) -> list[tuple[int, str]]:
    """Detect numbered clause headings in page text.

    Finds patterns such as '14.', '14.1', 'Section 14', 'Clause 14.1', 'ARTICLE IV'.
    Returns a list of (start_offset, section_label).
    Returns an empty list when no structure was found; never guesses.
    """
    if not page_text or not page_text.strip():
        return []

    results: list[tuple[int, str]] = []
    for match in _SECTION_PATTERN.finditer(page_text):
        label = match.group(1).strip()
        results.append((match.start(1), label))

    return results
