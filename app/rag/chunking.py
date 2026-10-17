"""Deterministic chunking strategies with stable chunk IDs (``PB-004#c02``)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.corpus import Document, clean_text

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str  # text used for indexing (includes title + section for context)


def _windows(words: list[str], size: int, overlap: int) -> list[list[str]]:
    if len(words) <= size:
        return [words]
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(words), step):
        out.append(words[start:start + size])
        if start + size >= len(words):
            break
    return out


def chunk_fixed(doc: Document, size: int = 120, overlap: int = 20) -> list[Chunk]:
    """Naive baseline: fixed word windows over the whole cleaned document."""
    words = clean_text(doc.content).split()
    return [
        Chunk(f"{doc.doc_id}#c{i:02d}", doc.doc_id, doc.title, "", " ".join(w))
        for i, w in enumerate(_windows(words, size, overlap))
    ]


def chunk_sections(doc: Document, max_words: int = 220, overlap: int = 30) -> list[Chunk]:
    """Heading-aware chunking: one chunk per ``##`` section, prefixed with doc title and heading.

    Long sections are split into overlapping windows so no chunk exceeds ``max_words``.
    """
    body = doc.content
    matches = list(_SECTION_RE.finditer(body))
    sections: list[tuple[str, str]] = []
    if not matches:
        sections.append(("", body))
    else:
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            sections.append((m.group(1).strip(), body[m.end():end]))
    chunks: list[Chunk] = []
    idx = 0
    for heading, text in sections:
        words = clean_text(text).split()
        if not words:
            continue
        for window in _windows(words, max_words, overlap):
            prefix = f"{doc.title}. {heading}." if heading else f"{doc.title}."
            chunks.append(Chunk(f"{doc.doc_id}#c{idx:02d}", doc.doc_id, doc.title, heading,
                                f"{prefix} {' '.join(window)}"))
            idx += 1
    return chunks


def chunk_corpus(docs: list[Document], strategy: str) -> list[Chunk]:
    if strategy == "fixed":
        fn = chunk_fixed
    elif strategy == "section":
        fn = chunk_sections
    else:
        raise ValueError(f"unknown chunking strategy {strategy!r}")
    return [c for d in docs for c in fn(d)]
