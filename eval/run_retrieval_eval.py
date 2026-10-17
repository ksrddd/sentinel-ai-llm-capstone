"""Reproducible retrieval experiment: BM25 baseline vs dense / hybrid candidates.

Protocol
--------
1. Every configuration ranks the corpus for every query (top 5 documents).
2. For each configuration the abstention threshold is tuned on the DEV split only
   (maximise dev abstention accuracy; ties -> lowest threshold).
3. The configuration to ship is selected on DEV only by mean(Recall@3, MRR@5),
   tie-break by dev abstention accuracy, then by list order (simpler first).
4. Baseline and selected configuration are then reported on the held-out TEST split.
   All configurations are also reported on TEST for transparency, but TEST numbers
   are never used for any choice.

Usage:  python -m eval.run_retrieval_eval [--no-sbert]
Outputs: eval/results/{retrieval_runs.json, per_example.csv, selected_config.json,
         retrieval_summary.json}
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.chunking import chunk_corpus  # noqa: E402
from app.rag.corpus import corpus_fingerprint, load_corpus  # noqa: E402
from app.rag.dense import LSA_SEED, SBERT_MODEL, make_embedder  # noqa: E402
from app.rag.retriever import BM25_SAT_K, Retriever  # noqa: E402
from eval.metrics import (  # noqa: E402
    hit_at_k,
    mean,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
)

DATASET = ROOT / "eval" / "datasets" / "retrieval_eval_v1.jsonl"
RESULTS = ROOT / "eval" / "results"
BASELINE = "bm25-fixed"


def configurations(include_sbert: bool) -> list[dict]:
    cfgs = [
        {"name": "bm25-fixed", "method": "bm25", "chunking": "fixed", "backend": None, "alpha": None},
        {"name": "bm25-section", "method": "bm25", "chunking": "section", "backend": None, "alpha": None},
        {"name": "dense-lsa-fixed", "method": "dense", "chunking": "fixed", "backend": "lsa", "alpha": None},
        {"name": "dense-lsa-section", "method": "dense", "chunking": "section", "backend": "lsa", "alpha": None},
    ]
    for a in (0.3, 0.5, 0.7):
        cfgs.append({"name": f"hybrid-lsa-section-a{a}", "method": "hybrid", "chunking": "section",
                     "backend": "lsa", "alpha": a})
    if include_sbert:
        cfgs += [
            {"name": "dense-sbert-fixed", "method": "dense", "chunking": "fixed", "backend": "sbert", "alpha": None},
            {"name": "dense-sbert-section", "method": "dense", "chunking": "section", "backend": "sbert", "alpha": None},
        ]
        for a in (0.3, 0.5, 0.7):
            cfgs.append({"name": f"hybrid-sbert-section-a{a}", "method": "hybrid", "chunking": "section",
                         "backend": "sbert", "alpha": a})
    return cfgs


def load_dataset() -> list[dict]:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        assert r["split"] in {"dev", "test"}, r["id"]
        assert bool(r["relevant_document_ids"]) != r["expected_abstention"], r["id"]
    return rows


def tune_threshold(top_scores: list[float], expected: list[bool]) -> tuple[float, float]:
    """Pick the threshold maximising abstention accuracy on the given (dev) queries."""
    s = sorted(set(top_scores))
    candidates = [0.0] + [(a + b) / 2 for a, b in zip(s, s[1:], strict=False)] + [s[-1] + 1e-6]
    best_t, best_acc = 0.0, -1.0
    for t in candidates:
        acc = mean([float((score < t) == exp) for score, exp in zip(top_scores, expected, strict=True)])
        if acc > best_acc + 1e-12:
            best_t, best_acc = t, acc
    return round(best_t, 6), best_acc


def evaluate(rows: list[dict], ranked: dict[str, list[str]], top: dict[str, float], threshold: float):
    answerable = [r for r in rows if r["relevant_document_ids"]]
    per = []
    for r in rows:
        ids = ranked[r["id"]]
        rel = r["relevant_document_ids"]
        abstained = top[r["id"]] < threshold or top[r["id"]] <= 0.0
        per.append({
            "id": r["id"], "split": r["split"], "scenario": r["scenario"],
            "relevant": "|".join(rel), "ranked_top5": "|".join(ids), "top_score": round(top[r["id"]], 6),
            "recall@3": round(recall_at_k(ids, rel, 3), 4) if rel else "",
            "rr@5": round(reciprocal_rank_at_k(ids, rel, 5), 4) if rel else "",
            "abstained": abstained, "expected_abstention": r["expected_abstention"],
            "abstention_correct": abstained == r["expected_abstention"],
        })
    metrics = {
        "n_queries": len(rows),
        "n_answerable": len(answerable),
        "recall@3": mean([recall_at_k(ranked[r["id"]], r["relevant_document_ids"], 3) for r in answerable]),
        "mrr@5": mean([reciprocal_rank_at_k(ranked[r["id"]], r["relevant_document_ids"], 5) for r in answerable]),
        "precision@3": mean([precision_at_k(ranked[r["id"]], r["relevant_document_ids"], 3) for r in answerable]),
        "hit@1": mean([hit_at_k(ranked[r["id"]], r["relevant_document_ids"], 1) for r in answerable]),
        "abstention_accuracy": mean([float(p["abstention_correct"]) for p in per]),
        "false_abstentions": sum(1 for p in per if p["abstained"] and not p["expected_abstention"]),
        "missed_abstentions": sum(1 for p in per if not p["abstained"] and p["expected_abstention"]),
    }
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items()}, per


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-sbert", action="store_true", help="skip the optional neural embedding backend")
    args = parser.parse_args()

    include_sbert = not args.no_sbert
    if include_sbert:
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            print("sentence-transformers not installed; skipping sbert configurations")
            include_sbert = False

    rows = load_dataset()
    docs = load_corpus(ROOT / "corpus" / "raw")
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]
    embedders: dict[tuple[str, str], object] = {}

    runs, per_rows = [], []
    for cfg in configurations(include_sbert):
        chunks = chunk_corpus(docs, cfg["chunking"])
        emb = None
        if cfg["backend"]:
            key = (cfg["backend"], cfg["chunking"])
            if key not in embedders:
                embedders[key] = make_embedder(cfg["backend"]).fit([c.text for c in chunks])
            emb = embedders[key]
        retr = Retriever(docs, chunks, cfg["method"], embedder=emb, alpha=cfg["alpha"] or 0.5)
        ranked, top = {}, {}
        for r in rows:
            hits = retr.rank_documents(r["query"], k=5)
            ranked[r["id"]] = [h.doc_id for h in hits]
            top[r["id"]] = hits[0].score if hits else 0.0
        threshold, _ = tune_threshold([top[r["id"]] for r in dev], [r["expected_abstention"] for r in dev])
        dev_m, dev_per = evaluate(dev, ranked, top, threshold)
        test_m, test_per = evaluate(test, ranked, top, threshold)
        runs.append({**cfg, "n_chunks": len(chunks), "threshold": threshold, "dev": dev_m, "test": test_m})
        for p in dev_per + test_per:
            per_rows.append({"config": cfg["name"], **p})
        print(f"{cfg['name']:<28} dev R@3={dev_m['recall@3']:.3f} MRR@5={dev_m['mrr@5']:.3f} "
              f"abst={dev_m['abstention_accuracy']:.3f} | test R@3={test_m['recall@3']:.3f} "
              f"MRR@5={test_m['mrr@5']:.3f} abst={test_m['abstention_accuracy']:.3f}")

    def dev_key(run: dict) -> tuple:
        d = run["dev"]
        return ((d["recall@3"] + d["mrr@5"]) / 2, d["abstention_accuracy"])

    best_key = max(dev_key(r) for r in runs)
    selected = next(r for r in runs if dev_key(r) == best_key)  # first in list order = simplest
    baseline = next(r for r in runs if r["name"] == BASELINE)

    # Paired per-query comparison on TEST (answerable queries).
    def rr_map(name: str) -> dict[str, float]:
        return {p["id"]: p["rr@5"] for p in per_rows
                if p["config"] == name and p["split"] == "test" and p["rr@5"] != ""}
    b_rr, s_rr = rr_map(BASELINE), rr_map(selected["name"])
    wins = sum(1 for q in b_rr if s_rr[q] > b_rr[q])
    losses = sum(1 for q in b_rr if s_rr[q] < b_rr[q])

    failures = [p for p in per_rows if p["config"] == selected["name"] and p["split"] == "test"
                and ((p["recall@3"] != "" and p["recall@3"] < 1.0) or not p["abstention_correct"])]

    dataset_sha = hashlib.sha256(DATASET.read_bytes()).hexdigest()[:16]
    meta = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "python -m eval.run_retrieval_eval" + (" --no-sbert" if args.no_sbert else ""),
        "dataset": DATASET.relative_to(ROOT).as_posix(), "dataset_sha256_16": dataset_sha,
        "dataset_counts": {"total": len(rows), "dev": len(dev), "test": len(test),
                           "dev_answerable": sum(1 for r in dev if r["relevant_document_ids"]),
                           "test_answerable": sum(1 for r in test if r["relevant_document_ids"])},
        "corpus_fingerprint": corpus_fingerprint(docs), "corpus_documents": len(docs),
        "seeds": {"lsa_truncated_svd_random_state": LSA_SEED},
        "embedding_models": {"lsa": "TF-IDF(1-2 gram, sublinear) + TruncatedSVD(<=96 dims, arpack)",
                             "sbert": SBERT_MODEL if include_sbert else "not run"},
        "bm25": {"k1": 1.5, "b": 0.75, "hybrid_saturation_k": BM25_SAT_K},
        "selection_rule": "max dev mean(Recall@3, MRR@5); tie-break dev abstention accuracy; then list order",
        "python": platform.python_version(),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "retrieval_runs.json").write_text(json.dumps({"meta": meta, "runs": runs}, indent=2), "utf-8")
    with (RESULTS / "per_example.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(per_rows[0].keys()))
        writer.writeheader()
        writer.writerows(per_rows)
    selected_cfg = {k: selected[k] for k in ("name", "method", "chunking", "backend", "alpha", "threshold")}
    (RESULTS / "selected_config.json").write_text(json.dumps(selected_cfg, indent=2), "utf-8")
    summary = {
        "meta": meta,
        "baseline": {"name": baseline["name"], "threshold": baseline["threshold"], "test": baseline["test"],
                     "dev": baseline["dev"]},
        "selected": {**selected_cfg, "test": selected["test"], "dev": selected["dev"]},
        "test_paired_rr@5_vs_baseline": {"wins": wins, "losses": losses,
                                         "ties": len(b_rr) - wins - losses},
        "selected_test_failures": failures,
    }
    (RESULTS / "retrieval_summary.json").write_text(json.dumps(summary, indent=2), "utf-8")
    print(f"\nSelected on dev: {selected['name']} (threshold {selected['threshold']})")
    print(f"TEST baseline {BASELINE}: {baseline['test']}")
    print(f"TEST selected {selected['name']}: {selected['test']}")
    print(f"Paired RR@5 on test vs baseline: wins={wins} losses={losses}")


if __name__ == "__main__":
    main()
