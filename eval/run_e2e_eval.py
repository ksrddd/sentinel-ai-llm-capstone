"""End-to-end application evaluation against the live class proxy (gemma-4-E4B-it).

python -m eval.run_e2e_eval [--split test|dev|all] [--dataset PATH] [--round NAME]

The default (retrieval_eval_v1, test split) writes e2e_summary.json / e2e_results.jsonl; any other
split or dataset writes e2e_summary_<tag>.json / e2e_results_<tag>.jsonl so runs never overwrite each other.

For every labelled case with an expected incident type (answerable, ambiguous,
false-positive and insufficient-evidence scenarios) the query text is submitted as an
alert to the full pipeline. Metrics (denominator in brackets):
* valid_structured_output_rate  [cases run]          - pipeline returned a validated report
* incident_type_accuracy        [valid reports]
* severity_accuracy             [valid reports with an expected severity]
* citation_validity_rate        [citations in valid reports] - cited doc_id was retrieved in that run
* relevant_citation_rate        [valid reports with relevant docs] - >=1 labelled relevant doc cited
* undetermined_flagged_rate     [insufficient-evidence cases] - flagged for human review

Without OPENAI_API_KEY / OPENAI_BASE_URL the script exits with status 2 and writes nothing:
results are reported as pending rather than invented.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import MissingConfigError, Settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.schemas.alert import AlertSubmission  # noqa: E402
from app.services.analysis import AnalysisError  # noqa: E402
from eval.metrics import mean  # noqa: E402

DATASET = ROOT / "eval" / "datasets" / "retrieval_eval_v1.jsonl"
RESULTS = ROOT / "eval" / "results"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--dataset", type=Path, default=DATASET)
    ap.add_argument("--round", default=None, help="also archive outputs under eval/results/rounds/<ROUND>/")
    args = ap.parse_args()
    settings = Settings.from_env()
    try:
        settings.require_llm()
    except MissingConfigError as exc:
        print(f"PENDING - live evaluation not run: {exc}")
        return 2
    settings = replace(settings, db_path=RESULTS / "e2e_eval.db")
    c = build_container(settings)
    dataset = args.dataset.resolve()
    if dataset == DATASET:
        tag = "" if args.split == "test" else f"_{args.split}"
    else:
        tag = f"_{dataset.stem}_{args.split}"
    rows = [json.loads(x) for x in dataset.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if r["expected_incident_type"] and (args.split == "all" or r["split"] == args.split)]

    per = []
    for r in rows:
        t0 = time.perf_counter()
        rec = {"id": r["id"], "scenario": r["scenario"], "expected_type": r["expected_incident_type"],
               "expected_severity": r["expected_severity"], "relevant": r["relevant_document_ids"]}
        try:
            out = c.analysis.analyze(AlertSubmission(content=r["query"], label=f"eval {r['id']}"))
            rep = out["report"]
            retrieved = {h["doc_id"] for h in out["retrieved"]}
            cited = [x["doc_id"] for x in rep["source_citations"]]
            rec.update(valid=True, predicted_type=rep["incident_type"], predicted_severity=rep["severity"],
                       factors=rep["severity_assessment"]["factors"],
                       cited=cited, citations_valid=sum(1 for d in cited if d in retrieved),
                       requires_review=rep["requires_human_review"], agent_stop=out["agent_trace"]["stop_reason"],
                       agent_mode=out["agent_trace"]["mode"], tools=out["agent_trace"]["tools_used"],
                       attempts=out["attempts"])
        except AnalysisError as exc:
            rec.update(valid=False, error_stage=exc.stage, error=str(exc)[:300])
        rec["seconds"] = round(time.perf_counter() - t0, 1)
        per.append(rec)
        print(json.dumps(rec)[:240])

    valid = [p for p in per if p["valid"]]
    sev = [p for p in valid if p["expected_severity"]]
    rel = [p for p in valid if p["relevant"]]
    insuff = [p for p in valid if p["expected_type"] == "undetermined"]
    n_cit = sum(len(p["cited"]) for p in valid)
    agg = {
        "cases_run": len(per),
        "valid_structured_output_rate": round(len(valid) / len(per), 4) if per else None,
        "incident_type_accuracy": round(mean([float(p["predicted_type"] == p["expected_type"]) for p in valid]), 4)
        if valid else None,
        "severity_accuracy": round(mean([float(p["predicted_severity"] == p["expected_severity"]) for p in sev]), 4)
        if sev else None,
        "severity_cases": len(sev),
        "citation_validity_rate": round(sum(p["citations_valid"] for p in valid) / n_cit, 4) if n_cit else None,
        "relevant_citation_rate": round(mean([float(bool(set(p["cited"]) & set(p["relevant"]))) for p in rel]), 4)
        if rel else None,
        "undetermined_flagged_rate": round(mean([float(p["requires_review"]) for p in insuff]), 4) if insuff else None,
        "native_tool_mode_rate": round(mean([float(p["agent_mode"] == "native") for p in valid]), 4) if valid else None,
    }
    meta = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "model": settings.model,
            "temperature": settings.temperature, "split": args.split,
            "dataset": dataset.relative_to(ROOT).as_posix(), "round": args.round,
            "command": f"python -m eval.run_e2e_eval --split {args.split}"
                       + ("" if dataset == DATASET else f" --dataset {dataset.relative_to(ROOT).as_posix()}")
                       + (f" --round {args.round}" if args.round else ""),
            "retrieval": {"method": c.settings.retriever, "chunking": c.settings.chunking,
                          "backend": c.settings.dense_backend, "alpha": c.settings.hybrid_alpha,
                          "min_score": c.settings.min_score}}
    for out in [RESULTS] + ([RESULTS / "rounds" / args.round] if args.round else []):
        out.mkdir(parents=True, exist_ok=True)
        (out / f"e2e_results{tag}.jsonl").write_text("\n".join(json.dumps(p) for p in per) + "\n", encoding="utf-8")
        (out / f"e2e_summary{tag}.json").write_text(json.dumps({"meta": meta, "aggregate": agg}, indent=2), "utf-8")
    print(json.dumps(agg, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
