"""BM25 / dense / hybrid retrieval with document-level ranking and abstention.

Scores
------
* ``bm25``   - raw Okapi BM25 score of the best chunk.
* ``dense``  - cosine similarity of the best chunk (embeddings are L2-normalised).
* ``hybrid`` - ``alpha * cosine + (1 - alpha) * bm25 / (bm25 + BM25_SAT_K)``.
  The saturating transform keeps the lexical component query-independent in scale
  (0..1) so a single abstention threshold is meaningful across queries.

Documents are ranked by their best-scoring chunk. If the top document scores below
``min_score`` the retriever abstains (returns no hits) instead of returning weak matches.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from app.rag.bm25 import BM25Index
from app.rag.chunking import Chunk
from app.rag.corpus import Document

BM25_SAT_K = 8.0
METHODS = ("bm25", "dense", "hybrid")


@dataclass(frozen=True)
class RetrievalHit:
    doc_id: str
    title: str
    version: str
    chunk_id: str
    section: str
    score: float
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    method: str
    hits: list[RetrievalHit]
    abstained: bool
    top_score: float
    min_score: float


class Retriever:
    def __init__(self, docs: list[Document], chunks: list[Chunk], method: str, *,
                 embedder=None, chunk_embeddings: np.ndarray | None = None,
                 alpha: float = 0.5, min_score: float = 0.0) -> None:
        if method not in METHODS:
            raise ValueError(f"unknown retrieval method {method!r}")
        if method != "bm25" and embedder is None:
            raise ValueError(f"{method} retrieval needs an embedder")
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        self.docs = {d.doc_id: d for d in docs}
        self.chunks = chunks
        self.method = method
        self.alpha = alpha
        self.min_score = min_score
        self.embedder = embedder
        self.bm25 = BM25Index([c.text for c in chunks]) if method != "dense" else None
        self.chunk_emb = None
        if method != "bm25":
            self.chunk_emb = (chunk_embeddings if chunk_embeddings is not None
                              else embedder.embed([c.text for c in chunks]))

    def chunk_scores(self, query: str) -> np.ndarray:
        if self.method == "bm25":
            return self.bm25.scores(query)
        q = self.embedder.embed([query])[0]
        cos = self.chunk_emb @ q
        if self.method == "dense":
            return cos
        bm = self.bm25.scores(query)
        return self.alpha * cos + (1 - self.alpha) * (bm / (bm + BM25_SAT_K))

    def rank_documents(self, query: str, k: int = 5) -> list[RetrievalHit]:
        scores = self.chunk_scores(query)
        best: dict[str, tuple[float, int]] = {}
        for i, s in enumerate(scores):
            doc_id = self.chunks[i].doc_id
            if doc_id not in best or s > best[doc_id][0]:
                best[doc_id] = (float(s), i)
        # Sort by score desc, then doc_id for deterministic tie-breaking.
        ranked = sorted(best.items(), key=lambda kv: (-kv[1][0], kv[0]))[:k]
        hits = []
        for doc_id, (score, idx) in ranked:
            c, d = self.chunks[idx], self.docs[doc_id]
            hits.append(RetrievalHit(doc_id, d.title, d.version, c.chunk_id, c.section,
                                     round(score, 6), c.text))
        return hits

    def search(self, query: str, k: int = 3, min_score: float | None = None) -> RetrievalResult:
        threshold = self.min_score if min_score is None else min_score
        hits = self.rank_documents(query, k)
        top = hits[0].score if hits else 0.0
        abstained = top < threshold or top <= 0.0
        return RetrievalResult(query, self.method, [] if abstained else hits, abstained, top, threshold)
