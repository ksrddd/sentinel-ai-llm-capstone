"""Label consistency checks for the committed evaluation dataset."""

import json
import re

import pytest

from app.core.config import ROOT_DIR
from app.rag.corpus import clean_text
from app.schemas.common import INCIDENT_TYPES

DATASET = ROOT_DIR / "eval" / "datasets" / "retrieval_eval_v1.jsonl"
ROWS = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
HOLDOUT_ROWS = [json.loads(line) for v in (2, 3, 4)
                for line in (ROOT_DIR / "eval" / "datasets" / f"e2e_holdout_v{v}.jsonl").read_text(
                    encoding="utf-8").splitlines() if line.strip()]


def test_dataset_size_and_ids():
    assert 28 <= len(ROWS) <= 35
    ids = [r["id"] for r in ROWS]
    assert len(ids) == len(set(ids))


def test_splits_are_balanced_and_disjoint():
    dev = {r["id"] for r in ROWS if r["split"] == "dev"}
    test = {r["id"] for r in ROWS if r["split"] == "test"}
    assert dev and test and not dev & test and len(dev | test) == len(ROWS)
    for split in ("dev", "test"):
        assert any(r["expected_abstention"] for r in ROWS if r["split"] == split)


def test_scenario_coverage():
    scenarios = {r["scenario"] for r in ROWS}
    for needed in ("answerable", "ambiguous", "similar_different_playbook", "insufficient_evidence",
                   "out_of_domain", "false_positive"):
        assert needed in scenarios


def test_holdout_is_separate_from_v1():
    assert len(HOLDOUT_ROWS) == 48 and {r["split"] for r in HOLDOUT_ROWS} == {"holdout"}
    ids = [r["id"] for r in HOLDOUT_ROWS]
    assert len(set(ids)) == len(ids) and not set(ids) & {r["id"] for r in ROWS}
    queries = [r["query"] for r in HOLDOUT_ROWS]
    assert len(set(queries)) == len(queries) and not set(queries) & {r["query"] for r in ROWS}


@pytest.mark.parametrize("row", ROWS + HOLDOUT_ROWS, ids=[r["id"] for r in ROWS + HOLDOUT_ROWS])
def test_row_labels_are_consistent(row, docs, severity_service):
    corpus_ids = {d.doc_id for d in docs}
    assert set(row["relevant_document_ids"]) <= corpus_ids
    assert row["expected_abstention"] == (not row["relevant_document_ids"])
    assert row["notes"]
    if row["expected_incident_type"] is not None:
        assert row["expected_incident_type"] in INCIDENT_TYPES
    if row["expected_severity"] is not None:
        f = row["severity_factors"]
        got = severity_service.assess(f["hostname"], f["alert_confidence"], f["observed_impact"],
                                      f["privileged_account"])
        assert got.asset_known, f"{row['id']}: hostname not in catalogue"
        assert got.severity == row["expected_severity"], f"{row['id']}: label disagrees with PB-002"
    else:
        assert row["severity_factors"] is None


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def test_queries_do_not_copy_corpus_wording(docs):
    corpus = set()
    for d in docs:
        corpus |= _ngrams(clean_text(d.content), 6)
    copied = {r["id"]: sorted(_ngrams(r["query"], 6) & corpus) for r in ROWS}
    assert not {k: v for k, v in copied.items() if v}
