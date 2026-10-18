"""BM25 lexical retrieval index for legal document chunks."""
from __future__ import annotations

import logging
import re
from rank_bm25 import BM25L

from backend.app.ingestion.normalizer import normalize_for_search
from backend.app.models.schemas import DocumentChunk
from backend.app.retrieval.base import ChunkSearcher

logger = logging.getLogger(__name__)

# NOTE: BM25 scores are lexical relevance rankings based on term frequency and
# inverse document frequency, NOT probabilities or legal confidence assessments.

# Standard English stop-word list to eliminate high-frequency, low-discrimination tokens
STOP_WORDS: frozenset[str] = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize normalized search text, removing stop-words.

    Never modifies original chunk text.
    """
    normalized = normalize_for_search(text)
    words = re.findall(r"[a-z0-9]+", normalized)
    return [w for w in words if w not in STOP_WORDS]


class Bm25Index(ChunkSearcher):
    """In-memory BM25 lexical search index over document chunks."""

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = list(chunks)
        if not self.chunks:
            self.bm25: BM25L | None = None
            self.tokenized_corpus: list[list[str]] = []
        else:
            self.tokenized_corpus = [_tokenize(c.text) for c in self.chunks]
            # Ensure at least one token exists across corpus to prevent rank_bm25 zero-division
            has_tokens = any(len(doc) > 0 for doc in self.tokenized_corpus)
            if has_tokens:
                self.bm25 = BM25L(self.tokenized_corpus)
            else:
                self.bm25 = None

    def search(
        self, query: str, top_k: int = 5
    ) -> list[tuple[DocumentChunk, float]]:
        """Search indexed chunks using BM25Okapi.

        Returns list of (DocumentChunk, score) sorted descending by relevance score.
        Scores are relevance rankings, not probabilities or legal confidence.
        """
        if not self.chunks or self.bm25 is None:
            return []

        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        scores = self.bm25.get_scores(q_tokens)
        scored_chunks: list[tuple[DocumentChunk, float]] = [
            (self.chunks[i], float(scores[i])) for i in range(len(self.chunks))
        ]
        scored_chunks.sort(key=lambda item: item[1], reverse=True)
        return scored_chunks[:top_k]
