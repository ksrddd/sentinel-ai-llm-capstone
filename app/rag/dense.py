"""Dense embedding backends.

* ``lsa``   - TF-IDF (uni+bigram) projected with truncated SVD (latent semantic analysis).
              Fully local, deterministic (``random_state=42``), no downloads. Default.
* ``sbert`` - Sentence Transformers ``all-MiniLM-L6-v2`` (optional ``[neural]`` extra).
              Downloads the model from the Hugging Face hub on first use.

The required Gemma model is used for reasoning/generation only; embeddings are a
separate, documented component.
"""

from __future__ import annotations

import numpy as np

from app.rag.text import tokenize

SBERT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Pinned Hugging Face commit (supply chain: a moved "main" branch cannot silently change embeddings).
SBERT_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
LSA_SEED = 42


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class LSAEmbedder:
    name = "lsa"

    def __init__(self, n_components: int = 96) -> None:
        self.n_components = n_components
        self._vec = None
        self._svd = None

    def fit(self, texts: list[str]) -> LSAEmbedder:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vec = TfidfVectorizer(tokenizer=tokenize, lowercase=False, token_pattern=None,
                                    ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        x = self._vec.fit_transform(texts)
        k = max(2, min(self.n_components, x.shape[0] - 1, x.shape[1] - 1))
        self._svd = TruncatedSVD(n_components=k, random_state=LSA_SEED, algorithm="arpack")
        self._svd.fit(x)
        return self

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._vec is None or self._svd is None:
            raise RuntimeError("LSAEmbedder must be fit before embed")
        return _normalize(self._svd.transform(self._vec.transform(texts)))


class SBERTEmbedder:
    name = "sbert"

    def __init__(self, model_name: str = SBERT_MODEL) -> None:
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.model_name = model_name
        self._model = SentenceTransformer(model_name, device="cpu", revision=SBERT_REVISION)

    def fit(self, texts: list[str]) -> SBERTEmbedder:  # pretrained: nothing to fit
        return self

    def embed(self, texts: list[str]) -> np.ndarray:
        emb = self._model.encode(texts, batch_size=32, show_progress_bar=False,
                                 normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(emb, dtype=np.float32)


def make_embedder(backend: str):
    if backend == "lsa":
        return LSAEmbedder()
    if backend == "sbert":
        return SBERTEmbedder()
    raise ValueError(f"unknown dense backend {backend!r}")
