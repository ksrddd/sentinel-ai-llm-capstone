"""Ingestion pipeline and persistent local index.

``python -m scripts.ingest`` writes ``data/index/<chunking>-<backend>/`` containing:
* ``manifest.json``   - corpus fingerprint, chunking, backend, model, chunk count,
* ``chunks.json``     - chunk ids, doc ids, sections and text,
* ``embeddings.npy``  - L2-normalised chunk embeddings (numpy, no pickle).

For the neural backend the stored embeddings are reused when the corpus fingerprint
matches. The LSA backend must re-fit its vocabulary to embed queries, which is
deterministic and takes well under a second, so it is refit on load and the stored
matrix is used only to verify reproducibility.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from app.rag.chunking import Chunk, chunk_corpus
from app.rag.corpus import Document, corpus_fingerprint, load_corpus
from app.rag.dense import SBERT_MODEL, make_embedder
from app.rag.retriever import Retriever


def index_path(index_dir: Path, chunking: str, backend: str) -> Path:
    return index_dir / f"{chunking}-{backend}"


def build_index(docs: list[Document], chunking: str, backend: str, out_dir: Path) -> dict:
    chunks = chunk_corpus(docs, chunking)
    embedder = make_embedder(backend).fit([c.text for c in chunks])
    emb = embedder.embed([c.text for c in chunks]).astype(np.float32)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "corpus_fingerprint": corpus_fingerprint(docs),
        "documents": len(docs),
        "chunks": len(chunks),
        "chunking": chunking,
        "dense_backend": backend,
        "embedding_model": SBERT_MODEL if backend == "sbert" else "tfidf-1-2gram+truncated-svd(seed=42)",
        "embedding_dim": int(emb.shape[1]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "chunks.json").write_text(json.dumps([asdict(c) for c in chunks], indent=1),
                                         encoding="utf-8")
    np.save(out_dir / "embeddings.npy", emb, allow_pickle=False)
    return manifest


def load_retriever(corpus_dir: Path, index_dir: Path, *, method: str, chunking: str,
                   backend: str, alpha: float, min_score: float) -> tuple[Retriever, list[Document]]:
    """Load (or build on the fly) a retriever. Falls back to in-memory build if no index exists."""
    docs = load_corpus(corpus_dir)
    chunks = chunk_corpus(docs, chunking)
    if method == "bm25":
        return Retriever(docs, chunks, "bm25", min_score=min_score), docs
    embedder = make_embedder(backend).fit([c.text for c in chunks])
    stored = None
    path = index_path(index_dir, chunking, backend)
    manifest_file = path / "manifest.json"
    if backend == "sbert" and manifest_file.is_file():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if manifest.get("corpus_fingerprint") == corpus_fingerprint(docs):
            saved_ids = [c["chunk_id"] for c in json.loads((path / "chunks.json").read_text("utf-8"))]
            if saved_ids == [c.chunk_id for c in chunks]:
                stored = np.load(path / "embeddings.npy", allow_pickle=False)
    retriever = Retriever(docs, chunks, method, embedder=embedder, chunk_embeddings=stored,
                          alpha=alpha, min_score=min_score)
    return retriever, docs


def load_chunks(path: Path) -> list[Chunk]:
    return [Chunk(**c) for c in json.loads((path / "chunks.json").read_text(encoding="utf-8"))]
