"""Okapi BM25 implemented directly (no external dependency)."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from app.rag.text import tokenize


class BM25Index:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(t)) for t in texts]
        self.lengths = np.array([sum(c.values()) for c in self.docs], dtype=float)
        self.avgdl = float(self.lengths.mean()) if len(self.docs) else 0.0
        df: Counter[str] = Counter()
        for c in self.docs:
            df.update(c.keys())
        n = len(self.docs)
        self.idf = {t: math.log((n - f + 0.5) / (f + 0.5) + 1.0) for t, f in df.items()}

    def scores(self, query: str) -> np.ndarray:
        q = tokenize(query)
        out = np.zeros(len(self.docs))
        for i, counts in enumerate(self.docs):
            denom_base = self.k1 * (1 - self.b + self.b * self.lengths[i] / (self.avgdl or 1.0))
            s = 0.0
            for term in q:
                tf = counts.get(term, 0)
                if tf:
                    s += self.idf[term] * tf * (self.k1 + 1) / (tf + denom_base)
            out[i] = s
        return out
