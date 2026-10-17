import pytest

from app.rag.chunking import chunk_corpus
from app.rag.dense import LSAEmbedder
from app.rag.retriever import Retriever
from eval.metrics import hit_at_k, precision_at_k, recall_at_k, reciprocal_rank_at_k


@pytest.mark.parametrize("query,expected", [
    ("dozens of failed password attempts from one address against an account", "PB-004"),
    ("encoded powershell launched by office document with hidden window", "PB-008"),
    ("long random subdomains and TXT queries to one parent domain", "PB-012"),
    ("who approves isolating a server during containment", "PB-016"),
])
def test_bm25_finds_expected_playbook(bm25_retriever, query, expected):
    ids = [h.doc_id for h in bm25_retriever.search(query, k=3).hits]
    assert expected in ids


def test_out_of_domain_query_abstains(bm25_retriever):
    res = bm25_retriever.search("best recipe for chocolate cake", k=3)
    assert res.abstained and res.hits == []


def test_ranking_is_deterministic_and_document_level(bm25_retriever):
    q = "beaconing to a rare external address every minute"
    a = bm25_retriever.rank_documents(q, 5)
    b = bm25_retriever.rank_documents(q, 5)
    assert [h.doc_id for h in a] == [h.doc_id for h in b]
    assert len({h.doc_id for h in a}) == len(a)  # one hit per document
    assert all(a[i].score >= a[i + 1].score for i in range(len(a) - 1))


def test_hits_cite_real_documents(bm25_retriever, docs):
    known = {d.doc_id: d for d in docs}
    for h in bm25_retriever.rank_documents("data exfiltration archive upload", 5):
        assert h.doc_id in known and h.title == known[h.doc_id].title and h.version == known[h.doc_id].version


@pytest.fixture(scope="module")
def lsa_hybrid(docs):
    chunks = chunk_corpus(docs, "section")
    emb = LSAEmbedder().fit([c.text for c in chunks])
    return Retriever(docs, chunks, "hybrid", embedder=emb, alpha=0.5)


def test_hybrid_scores_bounded(lsa_hybrid):
    hits = lsa_hybrid.rank_documents("suspicious dns tunnelling", 5)
    assert all(-1.0 <= h.score <= 1.0 for h in hits)


def test_invalid_retriever_configuration(docs):
    chunks = chunk_corpus(docs, "section")
    with pytest.raises(ValueError):
        Retriever(docs, chunks, "dense")  # missing embedder
    with pytest.raises(ValueError):
        Retriever(docs, chunks, "bm25", alpha=1.5)
    with pytest.raises(ValueError):
        Retriever(docs, chunks, "keyword")


def test_index_persistence_roundtrip(docs, tmp_path):
    import numpy as np

    from app.rag.index import build_index, load_chunks
    manifest = build_index(docs, "section", "lsa", tmp_path)
    assert manifest["documents"] == len(docs) and manifest["chunks"] == len(load_chunks(tmp_path))
    emb = np.load(tmp_path / "embeddings.npy", allow_pickle=False)
    assert emb.shape[0] == manifest["chunks"]
    assert np.allclose(np.linalg.norm(emb, axis=1), 1.0, atol=1e-4)


def test_lsa_embeddings_reproducible(docs):
    import numpy as np
    texts = [c.text for c in chunk_corpus(docs, "section")]
    a = LSAEmbedder().fit(texts).embed(texts[:5])
    b = LSAEmbedder().fit(texts).embed(texts[:5])
    assert np.allclose(a, b)


@pytest.mark.neural
def test_sbert_hybrid_retrieval(docs):
    pytest.importorskip("sentence_transformers")
    from app.rag.dense import SBERTEmbedder
    chunks = chunk_corpus(docs, "section")
    r = Retriever(docs, chunks, "hybrid", embedder=SBERTEmbedder(), alpha=0.3)
    assert r.rank_documents("password spraying against VPN accounts", 3)[0].doc_id == "PB-004"


# --- metric unit tests ------------------------------------------------------
@pytest.mark.parametrize("ranked,relevant,k,expected", [
    (["A", "B", "C"], ["B"], 3, 1.0),
    (["A", "B", "C"], ["D"], 3, 0.0),
    (["A", "B", "C", "D"], ["A", "D"], 3, 0.5),
])
def test_recall_at_k(ranked, relevant, k, expected):
    assert recall_at_k(ranked, relevant, k) == expected


@pytest.mark.parametrize("ranked,relevant,expected", [
    (["A", "B"], ["A"], 1.0), (["A", "B"], ["B"], 0.5), (["A", "B", "C", "D", "E", "F"], ["F"], 0.0),
])
def test_reciprocal_rank(ranked, relevant, expected):
    assert reciprocal_rank_at_k(ranked, relevant, 5) == expected


def test_recall_undefined_without_relevant():
    with pytest.raises(ValueError):
        recall_at_k(["A"], [], 3)


def test_precision_and_hit():
    assert precision_at_k(["A", "B", "C"], ["A", "C"], 3) == pytest.approx(2 / 3)
    assert hit_at_k(["A", "B"], ["B"], 1) == 0.0
