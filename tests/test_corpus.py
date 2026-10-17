import pytest

from app.rag.chunking import chunk_corpus
from app.rag.corpus import CorpusError, clean_text, corpus_fingerprint, parse_document

GOOD_HEADER = "---\ndoc_id: PB-900\ntitle: T\ncategory: c\nversion: 1\nsource: s\n---\n# Body\n\n## A\ntext"


def test_corpus_size_and_unique_ids(docs):
    assert 15 <= len(docs) <= 20
    ids = [d.doc_id for d in docs]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)


def test_every_document_has_metadata_and_fictional_label(docs):
    for d in docs:
        assert d.title and d.version and d.category and d.source
        assert "FICTIONAL POLICY NOTICE" in d.content, d.doc_id
        assert "synthetic" in d.source.lower()


def test_filename_prefix_matches_doc_id(docs):
    for d in docs:
        assert d.filename.startswith(d.doc_id + "_")


@pytest.mark.parametrize("text,msg", [
    ("no front matter", "missing front matter"),
    ("---\ndoc_id: PB-1\ntitle: t\ncategory: c\nversion: 1\nsource: s\n---\nbody", "invalid doc_id"),
    ("---\ndoc_id: PB-001\ntitle: t\n---\nbody", "missing fields"),
])
def test_parse_errors(text, msg):
    with pytest.raises(CorpusError, match=msg):
        parse_document(text, "x.md")


def test_parse_good_document():
    d = parse_document(GOOD_HEADER, "x.md")
    assert d.doc_id == "PB-900" and d.citation.startswith("[PB-900]")


def test_clean_text_removes_banner_and_heading_marks():
    out = clean_text("# Title\n\nFICTIONAL POLICY NOTICE: blah\n\n## Section\nBody")
    assert "FICTIONAL" not in out and "#" not in out and "Body" in out


@pytest.mark.parametrize("strategy", ["fixed", "section"])
def test_chunk_ids_stable_unique_and_traceable(docs, strategy):
    a = chunk_corpus(docs, strategy)
    b = chunk_corpus(docs, strategy)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert len({c.chunk_id for c in a}) == len(a)
    doc_ids = {d.doc_id for d in docs}
    for c in a:
        assert c.doc_id in doc_ids and c.chunk_id.startswith(c.doc_id + "#c")
        assert "FICTIONAL POLICY NOTICE" not in c.text


def test_unknown_chunking_strategy(docs):
    with pytest.raises(ValueError):
        chunk_corpus(docs, "random")


def test_fingerprint_changes_with_content(docs):
    from dataclasses import replace
    changed = [replace(docs[0], content=docs[0].content + " x")] + docs[1:]
    assert corpus_fingerprint(docs) != corpus_fingerprint(changed)
