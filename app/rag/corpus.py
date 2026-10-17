"""Corpus loading: front-matter parsing, validation, cleaning."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

DOC_ID_RE = re.compile(r"^PB-\d{3}$")
REQUIRED_FIELDS = ("doc_id", "title", "category", "version", "source")
_NOTICE_RE = re.compile(r"^FICTIONAL POLICY NOTICE:.*$", re.MULTILINE)


class CorpusError(ValueError):
    pass


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    category: str
    version: str
    source: str
    last_reviewed: str
    filename: str
    content: str  # markdown body without front matter

    @property
    def citation(self) -> str:
        return f"[{self.doc_id}] {self.title} (v{self.version}, {self.source})"

    def metadata(self) -> dict[str, str]:
        return {
            "doc_id": self.doc_id, "title": self.title, "category": self.category,
            "version": self.version, "source": self.source, "last_reviewed": self.last_reviewed,
        }


def parse_document(text: str, filename: str) -> Document:
    if not text.startswith("---"):
        raise CorpusError(f"{filename}: missing front matter")
    try:
        _, header, body = text.split("---", 2)
    except ValueError as exc:
        raise CorpusError(f"{filename}: malformed front matter") from exc
    meta: dict[str, str] = {}
    for line in header.strip().splitlines():
        if ":" not in line:
            raise CorpusError(f"{filename}: bad front-matter line {line!r}")
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
    if missing:
        raise CorpusError(f"{filename}: missing fields {missing}")
    if not DOC_ID_RE.match(meta["doc_id"]):
        raise CorpusError(f"{filename}: invalid doc_id {meta['doc_id']!r}")
    return Document(
        doc_id=meta["doc_id"], title=meta["title"], category=meta["category"],
        version=meta["version"], source=meta["source"], last_reviewed=meta.get("last_reviewed", ""),
        filename=filename, content=body.strip(),
    )


def load_corpus(corpus_dir: Path) -> list[Document]:
    files = sorted(corpus_dir.glob("*.md"))
    if not files:
        raise CorpusError(f"no markdown documents in {corpus_dir}")
    docs = [parse_document(p.read_text(encoding="utf-8"), p.name) for p in files]
    seen: set[str] = set()
    for doc in docs:
        if doc.doc_id in seen:
            raise CorpusError(f"duplicate doc_id {doc.doc_id}")
        seen.add(doc.doc_id)
    return sorted(docs, key=lambda d: d.doc_id)


def clean_text(markdown: str) -> str:
    """Remove the repeated fictional-policy banner and markdown noise for indexing.

    The banner is kept in the displayed document but removed from the index because it is
    identical in every file and only adds noise to lexical and semantic matching.
    """
    text = _NOTICE_RE.sub("", markdown)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def corpus_fingerprint(docs: list[Document]) -> str:
    h = hashlib.sha256()
    for d in docs:
        h.update(d.doc_id.encode())
        h.update(d.version.encode())
        h.update(d.content.encode("utf-8"))
    return h.hexdigest()[:16]
