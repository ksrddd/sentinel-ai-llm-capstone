"""Generate documentation figures from committed artifacts.

python -m scripts.make_figures
  -> docs/architecture/architecture.png
  -> docs/report/figures/retrieval_comparison.png   (read from eval/results/retrieval_runs.json)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INK, MUTED, ACCENT, WARN, OK = "#1d2733", "#5b6b7d", "#1e88c8", "#c98a12", "#1f9d6a"


def box(ax, x, y, w, h, title, sub="", color=ACCENT):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.015",
                                fc="white", ec=color, lw=1.6))
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=8.6 if len(title) < 17 else 7.4, weight="bold", color=INK)
    if sub:
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=6.6, color=MUTED)


def arrow(ax, x1, y1, x2, y2, label="", color=MUTED, rad=0.0):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.2, "shrinkA": 2, "shrinkB": 2,
                            "connectionstyle": f"arc3,rad={rad}"})
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.012, label, fontsize=6.3, color=MUTED, ha="center")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    box(ax, 0.02, 0.78, 0.17, 0.14, "Web dashboard", "static HTML/CSS/JS")
    box(ax, 0.25, 0.78, 0.17, 0.14, "FastAPI routers", "validation, HTTP errors")
    box(ax, 0.48, 0.78, 0.2, 0.14, "AnalysisService", "orchestration")
    box(ax, 0.75, 0.78, 0.22, 0.14, "LLM adapter", "OpenAI SDK -> class proxy\ngemma-4-E4B-it, T=0", WARN)

    box(ax, 0.30, 0.52, 0.18, 0.14, "1. Extraction", "Pydantic + repair loop")
    box(ax, 0.52, 0.52, 0.18, 0.14, "2. Grounding check", "drop values not in alert", OK)
    box(ax, 0.74, 0.52, 0.23, 0.14, "3. Agent loop", "native tools / JSON protocol\nmax steps, timeout, errors")

    box(ax, 0.52, 0.27, 0.14, 0.13, "search_playbooks", "allow-listed", OK)
    box(ax, 0.68, 0.27, 0.14, 0.13, "calculate_severity", "PB-002 matrix", OK)
    box(ax, 0.84, 0.27, 0.14, 0.13, "lookup_history", "SQLite, read-only", OK)

    box(ax, 0.02, 0.27, 0.22, 0.13, "4. Report drafting", "citation check vs retrieved IDs")
    box(ax, 0.27, 0.27, 0.2, 0.13, "5. Final report", "severity/evidence from code")

    box(ax, 0.40, 0.03, 0.2, 0.14, "Retriever", "BM25 + MiniLM hybrid\nthreshold abstention")
    box(ax, 0.63, 0.03, 0.17, 0.14, "Corpus + index", "19 synthetic playbooks\nnpy embeddings")
    box(ax, 0.83, 0.03, 0.15, 0.14, "Asset catalogue", "synthetic JSON")
    box(ax, 0.02, 0.03, 0.2, 0.14, "Evaluation", "32 labelled queries\ndev/test split")

    arrow(ax, 0.19, 0.85, 0.25, 0.85, "REST")
    arrow(ax, 0.42, 0.85, 0.48, 0.85)
    arrow(ax, 0.68, 0.85, 0.75, 0.85, "chat()")
    arrow(ax, 0.55, 0.78, 0.40, 0.66)
    arrow(ax, 0.48, 0.59, 0.52, 0.59)
    arrow(ax, 0.70, 0.59, 0.74, 0.59)
    arrow(ax, 0.82, 0.52, 0.59, 0.40)
    arrow(ax, 0.85, 0.52, 0.75, 0.40)
    arrow(ax, 0.90, 0.52, 0.91, 0.40)
    arrow(ax, 0.59, 0.27, 0.52, 0.17)
    arrow(ax, 0.60, 0.10, 0.63, 0.10)
    arrow(ax, 0.75, 0.27, 0.88, 0.17)
    ax.plot([0.50, 0.50, 0.13], [0.78, 0.46, 0.46], color=MUTED, lw=1.2)
    arrow(ax, 0.13, 0.46, 0.13, 0.40)
    ax.text(0.31, 0.47, "after the agent stops", fontsize=6.3, color=MUTED, ha="center")
    arrow(ax, 0.24, 0.335, 0.27, 0.335)
    arrow(ax, 0.22, 0.10, 0.40, 0.10, "same retriever code")
    ax.text(0.5, 0.975, "SentinelAI architecture and data flow", ha="center", fontsize=11, weight="bold", color=INK)
    out = ROOT / "docs" / "architecture" / "architecture.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out.relative_to(ROOT))


def retrieval_chart() -> None:
    data = json.loads((ROOT / "eval" / "results" / "retrieval_runs.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "eval" / "results" / "retrieval_summary.json").read_text(encoding="utf-8"))
    runs = data["runs"]
    names = [r["name"] for r in runs]
    metrics = [("recall@3", "Recall@3"), ("mrr@5", "MRR@5")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), dpi=200, sharey=True)
    for ax, split in zip(axes, ("dev", "test"), strict=True):
        y = range(len(runs))
        h = 0.38
        for i, (key, label) in enumerate(metrics):
            vals = [r[split][key] for r in runs]
            colors = [ACCENT if n == summary["selected"]["name"] else ("#8a97a6" if n == summary["baseline"]["name"]
                      else "#c5d3e0") for n in names]
            ax.barh([p + (i - 0.5) * h for p in y], vals, height=h, color=colors,
                    hatch="" if i == 0 else "///", edgecolor="white", label=label)
        ax.set_title(f"{split.upper()} split", fontsize=10)
        ax.set_xlim(0, 1)
        ax.grid(axis="x", alpha=0.3)
        ax.tick_params(labelsize=7)
    axes[0].set_yticks(range(len(runs)))
    axes[0].set_yticklabels(names, fontsize=7)
    axes[0].invert_yaxis()
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=7.5, frameon=False)
    fig.suptitle("Retrieval configurations (blue = selected on dev, grey = BM25 baseline)", fontsize=9.5)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out = ROOT / "docs" / "report" / "figures" / "retrieval_comparison.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    architecture()
    retrieval_chart()
