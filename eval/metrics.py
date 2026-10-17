"""Retrieval metrics.

Denominators
------------
* Ranking metrics (Recall@k, MRR@k, Precision@k, Hit@k) are averaged over *answerable*
  queries only (queries with at least one relevant document). Out-of-domain queries have
  no relevant documents, so recall is undefined for them and they are excluded.
* Abstention accuracy is averaged over *all* queries: a query is correct when the
  retriever abstains if and only if ``expected_abstention`` is true.
"""

from __future__ import annotations

from collections.abc import Sequence


def recall_at_k(ranked: Sequence[str], relevant: Sequence[str], k: int) -> float:
    if not relevant:
        raise ValueError("recall undefined without relevant documents")
    return len(set(ranked[:k]) & set(relevant)) / len(set(relevant))


def hit_at_k(ranked: Sequence[str], relevant: Sequence[str], k: int) -> float:
    return 1.0 if set(ranked[:k]) & set(relevant) else 0.0


def precision_at_k(ranked: Sequence[str], relevant: Sequence[str], k: int) -> float:
    return len(set(ranked[:k]) & set(relevant)) / k


def reciprocal_rank_at_k(ranked: Sequence[str], relevant: Sequence[str], k: int) -> float:
    rel = set(relevant)
    for i, doc_id in enumerate(ranked[:k], start=1):
        if doc_id in rel:
            return 1.0 / i
    return 0.0


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")
