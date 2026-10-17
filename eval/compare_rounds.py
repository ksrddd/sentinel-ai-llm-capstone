"""Build the round-by-round comparison of end-to-end results.

python -m eval.compare_rounds

Reads every ``eval/results/rounds/<round>/e2e_summary*.json`` written by
``python -m eval.run_e2e_eval --round <round>`` and writes ``eval/results/rounds/rounds_summary.json``.
It also refreshes the generated table in ``docs/EXPERIMENT_LOG.md`` (between the marker comments).
Numbers are copied from the result files only; a missing run is shown as "-" and never estimated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = ROOT / "eval" / "results" / "rounds"
LOG = ROOT / "docs" / "EXPERIMENT_LOG.md"
BEGIN, END = "<!-- rounds-table:begin -->", "<!-- rounds-table:end -->"

# summary file suffix -> label; "seen" marks data whose failures were inspected before a later round
SETS = {
    "": "test v1 (12)",
    "_dev": "dev v1 (13)",
    "_e2e_holdout_v2_all": "holdout v2 (16)",
    "_e2e_holdout_v3_all": "holdout v3 (16)",
    "_e2e_holdout_v4_all": "holdout v4 (16)",
}
METRICS = {
    "severity_accuracy": "Severity acc.",
    "relevant_citation_rate": "Relevant citation",
    "incident_type_accuracy": "Type acc.",
    "citation_validity_rate": "Citation validity",
    "valid_structured_output_rate": "Valid output",
}


def collect() -> dict:
    out: dict = {}
    for rdir in sorted(p for p in ROUNDS.iterdir() if p.is_dir()):
        out[rdir.name] = {}
        for suffix, label in SETS.items():
            f = rdir / f"e2e_summary{suffix}.json"
            if f.is_file():
                out[rdir.name][label] = json.loads(f.read_text(encoding="utf-8"))["aggregate"]
    return out


def table(data: dict) -> str:
    lines = []
    for key, name in METRICS.items():
        lines += [f"**{name}**", "", "| Round | " + " | ".join(SETS.values()) + " |",
                  "|---|" + "---|" * len(SETS)]
        for rnd, sets in data.items():
            cells = [f"{sets[s][key]:.3f}" if s in sets and sets[s].get(key) is not None else "-"
                     for s in SETS.values()]
            lines.append(f"| {rnd} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    data = collect()
    (ROUNDS / "rounds_summary.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = table(data)
    print(md)
    if LOG.is_file():
        text = LOG.read_text(encoding="utf-8")
        if BEGIN in text and END in text:
            head, rest = text.split(BEGIN, 1)
            _, tail = rest.split(END, 1)
            LOG.write_text(f"{head}{BEGIN}\n{md}{END}{tail}", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
