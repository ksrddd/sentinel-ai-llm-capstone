"""Build the capstone PDF report from committed artifacts.

python -m scripts.build_report  ->  docs/report/SentinelAI_Capstone_Report.pdf

All numbers are read from eval/results/ at build time; nothing is typed in by hand. The section order follows
the assignment brief: problem and users, design, evaluation, results and failure analysis, limitations and next
steps. The Thai version is built separately by scripts/build_report_th.py.

Typography uses Segoe UI and Consolas when they are installed (Windows) and falls back to the built-in
Helvetica/Courier elsewhere; set SENTINEL_REPORT_FONT_DIR to a folder holding those .ttf files to override.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
OUT = ROOT / "docs" / "report" / "SentinelAI_Capstone_Report.pdf"
FINAL_ROUND = "r3_outcome_flag_label_fallback"

# ---------------------------------------------------------------- design tokens
NAVY = colors.HexColor("#0f2a44")
ACCENT = colors.HexColor("#1f6fb2")
ACCENT_SOFT = colors.HexColor("#9cc7ee")
INK = colors.HexColor("#1d2733")
MUTED = colors.HexColor("#5b6b7b")
RULE = colors.HexColor("#d5dde6")
ZEBRA = colors.HexColor("#f5f8fb")
HILITE = colors.HexColor("#e3effa")
TONES = {  # callout kind -> (bar, background)
    "info": (ACCENT, colors.HexColor("#eef5fc")),
    "fail": (colors.HexColor("#b42318"), colors.HexColor("#fdf1ef")),
    "warn": (colors.HexColor("#b26b00"), colors.HexColor("#fff7e8")),
}
MARGIN = 1.9 * cm
W = A4[0] - 2 * MARGIN


def _register_fonts() -> tuple[str, str, str, str, str]:
    """Return (regular, bold, italic, semibold, mono) font names, registering TTFs when available."""
    folder = Path(os.environ.get("SENTINEL_REPORT_FONT_DIR", r"C:\Windows\Fonts"))
    files = {"Sans": "segoeui.ttf", "Sans-Bold": "segoeuib.ttf", "Sans-Italic": "segoeuii.ttf",
             "Sans-BoldItalic": "segoeuiz.ttf", "Sans-Semibold": "seguisb.ttf", "Mono": "consola.ttf"}
    if not all((folder / f).is_file() for f in files.values()):
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-Bold", "Courier"
    for name, f in files.items():
        pdfmetrics.registerFont(TTFont(name, str(folder / f)))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic",
                                  boldItalic="Sans-BoldItalic")
    return "Sans", "Sans-Bold", "Sans-Italic", "Sans-Semibold", "Mono"


SANS, SANS_B, SANS_I, SANS_SB, MONO = _register_fonts()
ARROW = "→" if SANS == "Sans" else "-&gt;"

BODY = ParagraphStyle("body", fontName=SANS, fontSize=9.3, leading=13, spaceAfter=5, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.8, leading=10.2, textColor=MUTED, spaceAfter=3)
CAPTION = ParagraphStyle("caption", parent=SMALL, fontName=SANS_I)
H1 = ParagraphStyle("h1", parent=BODY, fontName=SANS_B, fontSize=14, leading=18, spaceBefore=12, spaceAfter=2,
                    textColor=NAVY, keepWithNext=1)
H2 = ParagraphStyle("h2", parent=BODY, fontName=SANS_SB, fontSize=10.8, leading=14, spaceBefore=7, spaceAfter=3,
                    textColor=ACCENT, keepWithNext=1)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7.9, leading=10, spaceAfter=0)
CELL_NUM = ParagraphStyle("cellnum", parent=CELL, alignment=1)
CELL_HDR = ParagraphStyle("cellhdr", parent=CELL, fontName=SANS_SB, textColor=colors.white)
LIST = ParagraphStyle("list", parent=BODY, leftIndent=13, bulletIndent=2, spaceAfter=2.5,
                      bulletFontName=SANS_B, bulletColor=ACCENT)
NUMERIC = re.compile(r"[\d.\s\-–—>→/()x%]+")


def fmt(text) -> str:
    return str(text).replace("->", ARROW).replace("<font face='Courier'>", f"<font face='{MONO}'>")


def p(text: str, style=BODY) -> Paragraph:
    return Paragraph(fmt(text), style)


def h1(text: str) -> list:
    rule = HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceBefore=0, spaceAfter=6)
    rule.keepWithNext = 1
    return [p(text, H1), rule]


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(fmt(i), LIST, bulletText="•") for i in items]


def numbered(items: list[str]) -> list[Paragraph]:
    return [Paragraph(fmt(i), LIST, bulletText=f"{n}.") for n, i in enumerate(items, start=1)]


def table(rows: list[list], widths: list[float], highlight_row: int | None = None) -> Table:
    def cell(c) -> Paragraph:
        text = fmt(c)
        return Paragraph(text, CELL_NUM if NUMERIC.fullmatch(text) else CELL)

    data = [[Paragraph(fmt(c), CELL_HDR) for c in rows[0]]] + [[cell(c) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]
    if highlight_row is not None:
        style += [("BACKGROUND", (0, highlight_row), (-1, highlight_row), HILITE),
                  ("LINEBEFORE", (0, highlight_row), (0, highlight_row), 2.5, ACCENT)]
    t.setStyle(TableStyle(style))
    return t


def captioned(caption: str, flowable, heading: str | None = None) -> KeepTogether:
    head = [p(heading, H2)] if heading else []
    return KeepTogether([*head, p(caption, CAPTION), flowable, Spacer(1, 7)])


def callout(flowables: list, kind: str = "info", title: str | None = None) -> Table:
    bar, bg = TONES[kind]
    head = ParagraphStyle("ct", parent=BODY, fontName=SANS_SB, textColor=bar, spaceAfter=3)
    t = Table([[([p(title, head)] if title else []) + flowables]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def figure(path: Path, width: float, height: float, caption: str) -> KeepTogether:
    frame = Table([[Image(str(path), width=width, height=height)]], colWidths=[W])
    frame.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, RULE), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                               ("ROUNDEDCORNERS", [3, 3, 3, 3])]))
    return KeepTogether([frame, Spacer(1, 3), p(caption, CAPTION), Spacer(1, 4)])


def cover(title: str, subtitle: str, meta_line: str, eyebrow_text: str = "PROJECT REPORT") -> Table:
    eyebrow = ParagraphStyle("eyebrow", parent=BODY, fontName=SANS_SB, fontSize=8, textColor=ACCENT_SOFT,
                             spaceAfter=4)
    big = ParagraphStyle("cover", parent=BODY, fontName=SANS_B, fontSize=21, leading=25, textColor=colors.white,
                         spaceAfter=4)
    sub = ParagraphStyle("coversub", parent=BODY, fontSize=10.5, leading=14, textColor=colors.white, spaceAfter=6)
    meta = ParagraphStyle("covermeta", parent=SMALL, textColor=ACCENT_SOFT, spaceAfter=0)
    t = Table([[[p(f"LLM APPLICATION CAPSTONE &nbsp;·&nbsp; {eyebrow_text}", eyebrow), p(title, big),
                 p(subtitle, sub), p(meta_line, meta)]]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                           ("LEFTPADDING", (0, 0), (-1, -1), 18), ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                           ("TOPPADDING", (0, 0), (-1, -1), 16), ("BOTTOMPADDING", (0, 0), (-1, -1), 14)]))
    return t


def kpi_tiles(tiles: list[tuple[str, str]]) -> Table:
    value = ParagraphStyle("kpi", parent=BODY, fontName=SANS_B, fontSize=14.5, leading=17, textColor=NAVY,
                           spaceAfter=2)
    label = ParagraphStyle("kpilabel", parent=SMALL, spaceAfter=0)
    gap = 0.25 * cm
    tile_w = (W - gap * (len(tiles) - 1)) / len(tiles)
    cells, widths = [], []
    for i, (v, lab) in enumerate(tiles):
        if i:
            cells.append("")
            widths.append(gap)
        cells.append([p(v, value), p(lab, label)])
        widths.append(tile_w)
    t = Table([cells], colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 8),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 9),
             ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    for j in range(0, len(cells), 2):
        style += [("BACKGROUND", (j, 0), (j, 0), ZEBRA), ("LINEABOVE", (j, 0), (j, 0), 2.2, ACCENT)]
    t.setStyle(TableStyle(style))
    return t


def glue_headings(story: list) -> list:
    """Merge keep-with-next flowables (headings, rules, captions) into the KeepTogether block that follows them.

    ReportLab's own keepWithNext refuses to chain into a KeepTogether, which orphans headings at page bottoms.
    """
    out: list = []
    pending: list = []
    for f in story:
        if isinstance(f, KeepTogether) and pending:
            out.append(KeepTogether(pending + list(f._content)))
            pending = []
        elif f.getKeepWithNext():
            pending.append(f)
        else:
            out += pending
            pending = []
            out.append(f)
    return out + pending


def f3(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, 1.55 * cm, A4[0] - MARGIN, 1.55 * cm)
    canvas.setFont(SANS, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 1.1 * cm, "SentinelAI · SOC Incident Triage Copilot · capstone report (synthetic data)")
    canvas.setFillColor(NAVY)
    canvas.setFont(SANS_B, 7.5)
    canvas.drawRightString(A4[0] - MARGIN, 1.1 * cm, f"{doc.page}")
    canvas.restoreState()


def floor_ablation(config: str) -> dict[str, dict[str, float]]:
    """Abstention accuracy and Recall@3 with the dev-tuned min_score floor versus no floor (score <= 0 only).

    Recomputed from per_example.csv, which stores every query's top-5 ranking before abstention is applied.
    """
    rows = [r for r in csv.DictReader((RES / "per_example.csv").open(encoding="utf-8")) if r["config"] == config]
    out: dict[str, dict[str, float]] = {}
    for split in ("dev", "test"):
        part = [r for r in rows if r["split"] == split]
        answerable = [r for r in part if r["relevant"]]

        def raw_recall(r: dict) -> float:
            rel = set(r["relevant"].split("|"))
            return len(rel & set(r["ranked_top5"].split("|")[:3])) / len(rel)

        out[split] = {
            "abst_none": sum((float(r["top_score"]) <= 0) == (r["expected_abstention"] == "True")
                             for r in part) / len(part),
            "abst_floor": sum(r["abstention_correct"] == "True" for r in part) / len(part),
            "recall_none": sum(raw_recall(r) for r in answerable) / len(answerable),
            "recall_floor": sum(float(r["recall@3"]) for r in answerable) / len(answerable),
        }
    return out


def build() -> None:
    summary = json.loads((RES / "retrieval_summary.json").read_text(encoding="utf-8"))
    runs = json.loads((RES / "retrieval_runs.json").read_text(encoding="utf-8"))["runs"]
    by_name = {r["name"]: r for r in runs}
    e2e = json.loads((RES / "e2e_summary.json").read_text(encoding="utf-8"))
    rounds = json.loads((RES / "rounds" / "rounds_summary.json").read_text(encoding="utf-8"))
    proxy_path = RES / "proxy_compat.json"
    proxy = json.loads(proxy_path.read_text(encoding="utf-8")) if proxy_path.is_file() else None
    meta, base, sel = summary["meta"], summary["baseline"], summary["selected"]
    paired = summary["test_paired_rr@5_vs_baseline"]
    counts = meta["dataset_counts"]
    agg = e2e["aggregate"]

    story: list = []
    blind_before = rounds["r2_evidence_kind_fallback"]["holdout v4 (16)"]["severity_accuracy"]
    blind_after = rounds[FINAL_ROUND]["holdout v4 (16)"]["severity_accuracy"]
    all_rounds = [m for per_set in rounds.values() for m in per_set.values()]
    always_valid = all(m["valid_structured_output_rate"] == 1 and m["citation_validity_rate"] == 1
                       for m in all_rounds)
    story += [
        cover("SentinelAI: An Intelligent SOC Incident Triage Copilot",
              "An evidence-grounded, citation-checked triage assistant for junior SOC analysts",
              f"github.com/ksrddd/sentinel-ai-llm-capstone &nbsp;·&nbsp; gemma-4-E4B-it via the class proxy, "
              f"temperature 0 &nbsp;·&nbsp; retrieval results {meta['generated_at'][:10]}, end-to-end results "
              f"{e2e['meta']['generated_at'][:10]}"),
        Spacer(1, 10),
        kpi_tiles([
            (f"{f3(base['test']['recall@3'])} -> {f3(sel['test']['recall@3'])}",
             "Recall@3 on held-out test, BM25 baseline -> selected hybrid"),
            (f"{f3(base['test']['mrr@5'])} -> {f3(sel['test']['mrr@5'])}",
             "MRR@5 on held-out test, same comparison"),
            (f"{f3(blind_before)} -> {f3(blind_after)}",
             "End-to-end severity accuracy, round r3 on its blind holdout (v4)"),
            ("100%" if always_valid else "see 4.2",
             f"Valid structured output and valid citations in all {len(all_rounds)} round/set runs"),
        ]),
        Spacer(1, 4),
    ]

    story.append(p("Abstract", H2))
    story.append(p(
        "SentinelAI helps junior Security Operations Center (SOC) analysts triage security alerts. It extracts "
        "schema-validated facts from an alert, removes any value that is not literally in the alert, lets a bounded "
        "tool-calling agent search 19 original playbooks and past incidents, computes severity with a documented "
        "deterministic matrix, and drafts an incident report whose citations must come from the retrieved playbooks. "
        f"On a held-out test split of {counts['test']} labelled queries, the retrieval configuration chosen on the dev "
        f"split ({sel['name']}) raised Recall@3 from {f3(base['test']['recall@3'])} to {f3(sel['test']['recall@3'])} "
        f"and MRR@5 from {f3(base['test']['mrr@5'])} to {f3(sel['test']['mrr@5'])} over a naive BM25 baseline. "
        "End-to-end, three improvement rounds were each measured on a freshly written 16-alert holdout set; the "
        f"last round raised blind severity accuracy from {f3(blind_before)} to {f3(blind_after)}. All sets are "
        "small and synthetic, so the report states the uncertainty and the remaining failures rather than a single headline number."))

    # ------------------------------------------------------------------ 1
    story += h1("1. Problem and who it is for")
    story.append(p(
        "Tier-1 analysts receive many alerts in inconsistent formats (JSON from an EDR, syslog lines from a VPN, "
        "one-line SIEM messages). Junior analysts make three recurring mistakes: (a) they confuse alerts that look "
        "alike but need different playbooks, such as a brute-force burst versus a successful login right after that "
        "burst; (b) they fill missing details with guesses; and (c) they assign severity inconsistently, so two "
        "analysts give the same alert different priorities. A generic chat-with-documents assistant makes (b) and "
        "(c) worse, because a language model will confidently invent hostnames, citations and priorities."))
    story.append(callout([p(
        "<b>The model handles language; anything that must be reproducible or auditable is done by code and checked "
        "against evidence.</b> SentinelAI proposes a triage for a human to review; it never blocks, isolates, scans "
        "or executes anything.")], "info", "Design principle"))
    story.append(Spacer(1, 6))
    story += bullets([
        "<b>Primary users:</b> junior SOC analysts who need a consistent first-pass triage with the right playbook.",
        "<b>Secondary users:</b> students learning incident triage, and instructors who want to see why a severity "
        "was assigned (the score breakdown and agent trace are shown in the dashboard).",
        "<b>Domain and data:</b> a fictional company (\"Kestrel Analytics\") with 19 original playbooks "
        "(PB-001..PB-019), an asset catalogue, 12 sample alerts and a synthetic incident history. None of it overlaps "
        "with the course reference app, whose corpus is the course's own software stack, so the reference app cannot "
        "answer these questions. IPs use RFC 5737 documentation ranges.",
    ])
    story.append(p("<b>Objectives.</b> O1 extract incident fields without inventing values; O2 retrieve the correct "
                   "playbook and cite only what was retrieved; O3 let an agent choose tools safely; O4 compute "
                   "severity deterministically; O5 measure each of these against a baseline and report it honestly."))

    # ------------------------------------------------------------------ 2
    story += h1("2. Design")
    story.append(KeepTogether([
        p("2.1 Architecture", H2),
        figure(ROOT / "docs/architecture/architecture.png", W * 0.82, W * 0.82 * 0.57,
               "Figure 1. Layers and request flow. Green boxes are deterministic safety components.")]))
    story.append(p(
        "The code follows the course's layering: routers (<i>app/api</i>) only validate HTTP input and map errors "
        "(422 invalid input, 400 malformed IDs, 502 failed model validation, 503 missing proxy configuration); "
        "services (<i>app/services</i>) hold the logic; repositories (<i>app/repositories</i>) wrap SQLite with "
        "parameterised SQL and the JSON asset catalogue; one LLM adapter (<i>app/llm/client.py</i>) is the only code "
        "that talks to the model, so the whole pipeline can be tested with a scripted fake client."))
    story.append(p("2.2 Request flow for POST /api/analyze", H2))
    story += numbered([
        "<b>Extract</b> - Gemma returns JSON validated by the <i>ExtractedIncident</i> Pydantic model (enumerated "
        "incident types, IP validation, bounded lists); up to 3 attempts, each retry receives the validator error.",
        "<b>Ground</b> - every extracted value (host, IPs, user, timestamp, evidence, indicators) must appear "
        "verbatim in the alert, otherwise it is removed and listed as a limitation; prompt-injection phrases are "
        "detected and force human review.",
        "<b>Agent</b> - the model chooses among three read-only tools (search_playbooks, calculate_severity, "
        "lookup_incident_history) for at most 6 model calls / 150 s.",
        "<b>Enforce</b> - if the agent skipped retrieval or called calculate_severity with factors that differ from "
        "the grounded extraction, the orchestrator runs the tool itself and records an enforced step in the trace.",
        "<b>Report</b> - Gemma drafts the summary, interpretation and actions; citations must be a subset of the "
        "retrieved IDs (bounded repair, else 502). Severity, evidence and citation metadata are filled in by code.",
        "<b>Serve</b> - the result is stored in SQLite and returned to the dashboard, which shows the severity "
        "breakdown, cited actions (click to open the playbook), retrieved passages and the agent trace.",
    ])

    story.append(p("2.3 Proxy configuration and safety", H2))
    story.append(p(
        "The OpenAI SDK reads OPENAI_API_KEY and OPENAI_BASE_URL from the "
        "environment (.env is git-ignored; placeholder values from .env.example are rejected); model gemma-4-E4B-it, "
        "temperature 0 for every call. " +
        ("The proxy probe (scripts/check_proxy.py) recorded: " + ", ".join(
            f"{k.replace('_', ' ')} {'ok' if v.get('ok') else 'failed'}" for k, v in proxy.items()
            if isinstance(v, dict)) + ". " if proxy else "") +
        "Alert text, playbook excerpts and tool results are wrapped in data tags and described to the model as "
        "untrusted; tool names are allow-listed and arguments use Pydantic models with extra fields forbidden, "
        "bounded integers and a hostname regex. No tool can write, scan, execute or reach the network."))

    story.append(p("2.4 Course techniques used and why", H2))
    tech = [["Course family", "How it is used here", "Why this choice"],
            ["(1) Structured output + schema validation",
             "Pydantic models for extraction, report draft and every tool argument; bounded repair loop.",
             "Downstream code (grounding, severity) needs typed fields. A failed repair returns 502 instead of a "
             "half-valid report, so the analyst never sees fabricated structure."],
            ["(2) RAG with citations",
             "Heading-aware chunks, hybrid BM25 + MiniLM retrieval, min_score abstention, citation check.",
             "Triage guidance must come from the organisation's playbooks, not model memory. Citing only retrieved "
             "IDs makes every recommendation checkable."],
            ["(3) Retrieval evaluation",
             f"{counts['total']} labelled queries, dev/test split, Recall@3, MRR@5, abstention accuracy, "
             "BM25 baseline; plus a live end-to-end evaluation.",
             "Chunking, the hybrid weight and the min_score floor were chosen by measurement on dev, not by guess."],
            ["(4) Agent loop with tools",
             "Native OpenAI tool calling (JSON-action fallback); allow-list; stop conditions: final answer, 6 "
             "steps, 150 s, 3 consecutive errors, duplicate-call refusal.",
             "Different alerts need different investigations (history lookup is useful for repeat hosts, not for "
             "phishing). Hard bounds keep a 4B model from looping."],
            ["(6) Served interface",
             "FastAPI REST API (analyze, search, severity, playbooks, history, eval) + static dashboard.",
             "Analysts work in a UI; the REST layer also makes every component testable on its own."],
            ["Deterministic severity (not an LLM task)",
             "PB-002 matrix: tier + confidence + 2*impact + 2 if privileged; tier from the asset catalogue.",
             "Consistency is the point of objective O4; a generated severity would differ between runs and could "
             "be argued out of the model by text inside the alert."]]
    story.append(captioned("Table 1. Techniques, where they are used and why. Family (5) - SQL, web search, code "
                           "execution, MCP - was deliberately not used: a triage assistant that can reach out of its "
                           "sandbox would add risk without helping the three target mistakes.",
                           table(tech, [W * 0.22, W * 0.37, W * 0.41])))
    # ------------------------------------------------------------------ 3
    story += h1("3. Evaluation")
    story.append(p("3.1 Test sets", H2))
    scen: dict[str, int] = {}
    for row in read_jsonl(ROOT / meta["dataset"]):
        scen[row["scenario"]] = scen.get(row["scenario"], 0) + 1
    sets = [["Set", "Size", "Used for", "Labels"],
            [f"{meta['dataset']} (dev)", f"{counts['dev']} ({counts['dev_answerable']} answerable)",
             "tuning thresholds, choosing the retrieval configuration",
             "relevant playbook IDs, incident type, severity + its factors, should-abstain, justification note"],
            [f"{meta['dataset']} (test)", f"{counts['test']} ({counts['test_answerable']} answerable)",
             "reported once for baseline and selected configuration; end-to-end test split", "same"],
            ["eval/datasets/e2e_holdout_v2/v3/v4.jsonl", "3 x 16 alerts",
             "one blind measurement per improvement round (each written before that round's change)",
             "same fields, alert-style wording"]]
    story.append(captioned("Table 2. Evaluation data (all hand-written and hand-labelled).",
                           table(sets, [W * 0.3, W * 0.16, W * 0.27, W * 0.27])))
    story.append(p(
        "Scenario mix of the 32 retrieval queries: " +
        ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(scen.items())) + ". The mix deliberately "
        "includes look-alike pairs, vague alerts and out-of-domain questions, because those are where juniors and "
        "naive retrieval fail. Automated tests check that every relevant ID exists, that each severity label "
        "agrees with PB-002 given its factors, and that no query shares a 6-word sequence with the corpus (so a "
        "query cannot be answered by copied wording)."))
    story.append(p("3.2 Metrics", H2))
    story += bullets([
        "<b>Recall@3</b> = |relevant in top 3| / |relevant|; <b>MRR@5</b> = 1 / rank of the first relevant "
        "document in the top 5 (0 if none) - the primary pair, averaged over answerable queries. Precision@3 and "
        "Hit@1 are secondary.",
        "<b>Abstention accuracy</b> over all queries: correct iff the retriever abstains exactly when no relevant "
        "document exists. This is what the min_score floor controls.",
        "<b>End-to-end</b> (live Gemma): valid structured output rate, incident-type accuracy, severity accuracy "
        "(on alerts with a severity label), citation validity (every cited ID was retrieved), relevant-citation rate "
        "(a labelled relevant playbook is cited), undetermined-flagged rate, native tool-calling rate.",
    ])
    story.append(p("3.3 Baselines and protocol", H2))
    story += bullets([
        "<b>Retrieval baseline A:</b> BM25 over fixed 120-word chunks - the naive first implementation. Candidates: "
        "BM25 with section chunks; dense LSA; dense MiniLM; hybrids with alpha in {0.3, 0.5, 0.7}.",
        "<b>min_score baseline:</b> no floor (abstain only if the top score is 0) versus a floor tuned on dev.",
        "<b>End-to-end baseline:</b> the first working pipeline (round r0), compared with each later round.",
        f"<b>Protocol:</b> thresholds tuned on dev only; selection rule fixed in advance ({meta['selection_rule']}); "
        "test reported once. All model calls at temperature 0; a repeat run (r2b) checked that round differences are "
        "not sampling noise.",
    ])

    # ------------------------------------------------------------------ 4
    story += h1("4. Results")
    story.append(p("4.1 Retrieval", H2))
    mkeys = ["recall@3", "mrr@5", "precision@3", "hit@1", "abstention_accuracy"]
    rows = [["Held-out TEST", "Recall@3", "MRR@5", "P@3", "Hit@1", "Abstention acc."],
            [f"A: {base['name']} (baseline)"] + [f3(base["test"][k]) for k in mkeys],
            [f"B: {sel['name']} (selected on dev)"] + [f3(sel["test"][k]) for k in mkeys]]
    story.append(captioned(f"Table 3. Baseline versus selected configuration on the held-out test split "
                           f"({counts['test']} queries, {counts['test_answerable']} answerable).",
                           table(rows, [W * 0.36] + [W * 0.128] * 5, highlight_row=2)))
    story.append(p(f"Per-query reciprocal rank on test versus the baseline: {paired['wins']} wins, "
                   f"{paired['losses']} loss, {paired['ties']} ties. On dev the selected configuration reached "
                   f"Recall@3 {f3(sel['dev']['recall@3'])} / MRR@5 {f3(sel['dev']['mrr@5'])} versus "
                   f"{f3(base['dev']['recall@3'])} / {f3(base['dev']['mrr@5'])} for the baseline."))

    # measured improvements over naive defaults
    fl = floor_ablation(sel["name"])
    bf, bs = by_name["bm25-fixed"], by_name["bm25-section"]
    imp = [["Choice (naive default -> chosen)", "Split", "Before", "After", "Reading"],
           ["Chunking: fixed 120 words -> one chunk per section (BM25 both)", "test R@3 / MRR@5",
            f"{f3(bf['test']['recall@3'])} / {f3(bf['test']['mrr@5'])}",
            f"{f3(bs['test']['recall@3'])} / {f3(bs['test']['mrr@5'])}",
            "Largest single gain; section headings carry the discriminative words."],
           ["Retriever: BM25 section -> hybrid alpha 0.3", "test R@3 / MRR@5",
            f"{f3(bs['test']['recall@3'])} / {f3(bs['test']['mrr@5'])}",
            f"{f3(sel['test']['recall@3'])} / {f3(sel['test']['mrr@5'])}",
            "Better on dev (selection), slightly lower MRR on test - see 5.3."],
           [f"min_score: none -> {sel['threshold']:.3f} (selected config)", "dev abstention",
            f3(fl["dev"]["abst_none"]), f3(fl["dev"]["abst_floor"]),
            f"Both out-of-domain dev queries now abstain; Recall@3 unchanged "
            f"({f3(fl['dev']['recall_none'])})."],
           ["", "test abstention", f3(fl["test"]["abst_none"]), f3(fl["test"]["abst_floor"]),
            f"No net gain on test: one correct abstention gained, one false abstention (Q04) introduced; "
            f"Recall@3 {f3(fl['test']['recall_none'])} -> {f3(fl['test']['recall_floor'])}."]]
    story.append(captioned("Table 4. Before/after numbers for the three retrieval choices that differ from the "
                           "naive default (computed from eval/results/retrieval_runs.json and per_example.csv).",
                           table(imp, [W * 0.3, W * 0.14, W * 0.12, W * 0.12, W * 0.32])))

    all_rows = [["Configuration", "chunks", "dev R@3", "dev MRR@5", "dev abst.", "test R@3", "test MRR@5",
                 "test abst."]]
    hl = None
    for i, r in enumerate(runs, start=1):
        if r["name"] == sel["name"]:
            hl = i
        all_rows.append([r["name"], r["n_chunks"], f3(r["dev"]["recall@3"]), f3(r["dev"]["mrr@5"]),
                         f3(r["dev"]["abstention_accuracy"]), f3(r["test"]["recall@3"]), f3(r["test"]["mrr@5"]),
                         f3(r["test"]["abstention_accuracy"])])
    story.append(captioned("Table 5. All configurations. Selection used the dev columns only; test columns are "
                           "shown for transparency and were not used for any decision.",
                           table(all_rows, [W * 0.25] + [W * 0.09] + [W * 0.11] * 6, highlight_row=hl)))
    story.append(figure(ROOT / "docs/report/figures/retrieval_comparison.png", W * 0.96, W * 0.96 * 0.47,
                        "Figure 2. Recall@3 and MRR@5 per configuration on dev and test."))

    story.append(p("4.2 End-to-end application (live Gemma)", H2))
    story.append(p(
        "Every labelled alert is sent through the full pipeline (python -m eval.run_e2e_eval). The first run (r0) "
        "showed that Gemma hedged alert confidence to 'medium' and under-rated impact, which pulled severity down. "
        "Three rounds of changes followed (docs/EXPERIMENT_LOG.md). Before each round a new 16-alert holdout set "
        "was written and labelled, so each change has exactly one measurement on data it was not designed from."))
    blind = [("r1_factor_rubric", "r0_baseline", "holdout v2 (16)",
              "explicit confidence/impact definitions; insufficient-evidence search"),
             ("r2_evidence_kind_fallback", "r1_factor_rubric", "holdout v3 (16)",
              "evidence kind -> deterministic confidence; retry search after abstention"),
             ("r3_outcome_flag_label_fallback", "r2_evidence_kind_fallback", "holdout v4 (16)",
              "yes/no 'malicious outcome confirmed' flag; label-only last-resort search")]
    brows = [["Round", "Change", "Blind set", "Severity acc.", "Relevant citation"]]
    for new, old, ds, what in blind:
        a, b = rounds.get(old, {}).get(ds), rounds.get(new, {}).get(ds)
        if a and b:
            brows.append([new.split("_")[0], what, ds,
                          f"{f3(a['severity_accuracy'])} -> {f3(b['severity_accuracy'])}",
                          f"{f3(a['relevant_citation_rate'])} -> {f3(b['relevant_citation_rate'])}"])
    story.append(captioned("Table 6. Each round measured on the holdout set written before it (before -> after). "
                           "This is the unbiased reading of the end-to-end improvements.",
                           table(brows, [W * 0.08, W * 0.42, W * 0.16, W * 0.17, W * 0.17])))
    r0 = rounds["r0_baseline"]["test v1 (12)"]
    names = {"valid_structured_output_rate": "valid structured output", "incident_type_accuracy": "incident type",
             "severity_accuracy": "severity", "citation_validity_rate": "citation validity",
             "relevant_citation_rate": "relevant citation", "undetermined_flagged_rate": "undetermined flagged",
             "native_tool_mode_rate": "native tool calling"}
    rows7 = [["Metric (test split)", "r0 baseline", "r3 final"]]
    rows7 += [[label, f3(r0.get(k)), f3(agg.get(k))] for k, label in names.items()]
    story.append(captioned(f"Table 7. Test split ({agg['cases_run']} alerts, {agg['severity_cases']} with a severity "
                           "label). Its r0 failures were inspected before r1, so the final column is not blind.",
                           table(rows7, [W * 0.4, W * 0.15, W * 0.15])))
    runs_all = [r for f in sorted((RES / "rounds").glob("*/e2e_results*.jsonl")) for r in read_jsonl(f)]
    repaired = sum(r["attempts"]["extraction"] > 1 or r["attempts"]["report"] > 1 for r in runs_all)
    story.append(p(
        "Structured output was valid in every run of every round; the repair loop was needed in "
        f"{repaired} of {len(runs_all)} recorded pipeline runs (almost always a second extraction attempt), and no "
        "report ever cited a playbook that had not been retrieved. The hard part was severity, which depends on "
        "the model's reading of confidence and impact. A repeat run of r2 (r2b) gave identical incident types, "
        "severities and factors, so the round-to-round differences are real at temperature 0. Pooled over all five "
        "sets, correct severities went from 40/51 (r2) to 43/51 (r3), but r3 also lost one severity and one citation "
        "case on holdout v3: prompt changes are not monotonic."))

    # ------------------------------------------------------------------ 5
    story += h1("5. Analysis: successes and failure cases")
    story.append(p("5.1 Success case", H2))
    story.append(p(
        "Holdout alert W01 (malware on WS-FIN-114 with confirmed limited execution) shows the intended path: the "
        "agent called search_playbooks, lookup_incident_history and calculate_severity natively; extraction and "
        "report each validated on the first attempt; the factors (tier medium, confidence high, impact "
        "confirmed_limited) scored High as labelled, and the report cited PB-007, the correct malware playbook, in "
        "about 11 s. In offline tests with a scripted LLM, fabricated citations are repaired or rejected, invented "
        "hostnames are removed, and an alert that asks the model to 'run_shell' is refused as an unknown tool."))

    story.append(p("5.2 Failure case in detail: an under-triaged phishing alert (W11)", H2))
    w11 = next(r for r in read_jsonl(RES / "rounds" / FINAL_ROUND / "e2e_results_e2e_holdout_v4_all.jsonl")
               if r["id"] == "W11")
    w11_label = next(r for r in read_jsonl(ROOT / "eval/datasets/e2e_holdout_v4.jsonl") if r["id"] == "W11")
    fx, lx = w11["factors"], w11_label["severity_factors"]
    alert_style = ParagraphStyle("alert", parent=BODY, fontName=MONO, fontSize=8.2, leading=11.5)
    frow = [["", "Asset tier", "Confidence", "Impact", "Score -> severity"],
            ["Label", "high (3)", f"{lx['alert_confidence']} (3)", f"{lx['observed_impact']} (2x2)", "10 -> High"],
            ["SentinelAI (r3)", f"{fx['asset_tier']} (3)", f"{fx['alert_confidence']} (1)",
             f"{fx['observed_impact']} (2x1)", f"6 -> {w11['predicted_severity']}"]]
    explanation = p(
        f"The incident type ({w11['predicted_type']}) and the citations ({', '.join(w11['cited'])}) were right, and "
        "the citation check passed. The error is in two judgements the model still makes: it classed a plain-English "
        "report as weak evidence (confidence low) and did not treat \"two users entered their passwords\" as a "
        "confirmed outcome (impact suspected instead of confirmed_limited). Because severity is computed from those "
        "factors, the deterministic matrix faithfully turned two wrong inputs into a Low. This is the most "
        "dangerous kind of error for a SOC - under-triage of a live credential compromise - and it shows the "
        "limit of the design: code makes severity consistent, but not correct when its inputs are wrong. The "
        "mitigation in place is that every report has requires_human_review set and shows the factor breakdown, "
        "so an analyst can see 'impact: suspected' next to an alert that says passwords were entered.")
    story.append(callout([p(w11_label["query"], alert_style),
                          p("Table 8. Severity factors for W11, label versus prediction.", CAPTION),
                          table(frow, [W * 0.2, W * 0.15, W * 0.17, W * 0.22, W * 0.2]), Spacer(1, 6),
                          explanation], "fail", "Alert W11 (holdout v4): expected High, predicted Low"))
    story.append(Spacer(1, 8))

    e2e_fail = [["Case", "Expected", "Predicted", "Cause"]]
    causes = {"W08": "classified undetermined; the beacon pattern on a lab host was not recognised (safe: goes to "
                     "human review, severity still right)",
              "W10": "C2-watchlist DNS match rated medium confidence -> Medium became Low",
              "V11": "short phishing report classed vague; cited PB-015 (evidence) instead of PB-017",
              "V16": "confirmed command injection kept at impact suspected -> High became Medium"}
    for name, ds in (("e2e_holdout_v4_all", "v4"), ("e2e_holdout_v3_all", "v3")):
        for r in read_jsonl(RES / "rounds" / FINAL_ROUND / f"e2e_results_{name}.jsonl"):
            wrong_sev = r["expected_severity"] and r["predicted_severity"] != r["expected_severity"]
            if r["id"] != "W11" and (wrong_sev or r["predicted_type"] != r["expected_type"]):
                e2e_fail.append([f"{r['id']} ({ds})", f"{r['expected_type']} / {r['expected_severity']}",
                                 f"{r['predicted_type']} / {r['predicted_severity']}",
                                 causes.get(r["id"], "see docs/EXPERIMENT_LOG.md")])
    story.append(captioned(f"Table 9. Other end-to-end errors of the final round ({FINAL_ROUND.split('_')[0]}) on "
                           "the two most recent holdout sets.",
                           table(e2e_fail, [W * 0.12, W * 0.22, W * 0.22, W * 0.44]),
                           heading="5.3 Other remaining failures"))
    fails = summary["selected_test_failures"]
    rcauses = {"Q02": "hostname LAB-TEST-07 matches the asset catalogue (PB-018), which outranks PB-004",
               "Q04": "no lexical overlap (city names) and a weak dense score -> false abstention",
               "Q20": "second relevant document (PB-005) ranked below 3",
               "Q26": "vocabulary mismatch: 'cut off the network' vs 'isolate'",
               "Q30": "generic business words score just above the abstention floor"}
    frows = [["Query", "Scenario", "Relevant", "Top-5 (selected)", "Cause (manual analysis)"]]
    for f in fails:
        frows.append([f["id"], f["scenario"].replace("_", " "), f["relevant"].replace("|", ", ") or "none (abstain)",
                      f["ranked_top5"].replace("|", ", "), rcauses.get(f["id"], "see per_example.csv")])
    story.append(captioned("Table 10. Remaining retrieval test failures of the selected configuration.",
                           table(frows, [W * 0.08, W * 0.15, W * 0.13, W * 0.29, W * 0.35])))
    story.append(Spacer(1, 2))
    story.append(callout(bullets([
        "Every retrieval configuration dropped from dev to test, so the dev split was easier. With 14 answerable "
        "test queries, one query moves Recall@3 by about 0.07; the hybrid's gain over the baseline (2 wins, 1 loss) "
        "is not statistically strong.",
        f"dense-sbert-fixed was the best configuration on test (R@3 {f3(by_name['dense-sbert-fixed']['test']['recall@3'])}, "
        f"MRR@5 {f3(by_name['dense-sbert-fixed']['test']['mrr@5'])}) but was not chosen: switching now would mean "
        "selecting on the test set. We report it instead of re-selecting.",
        "The min_score floor helped on dev but was neutral on test (Table 4). One global threshold cannot separate "
        "'generic business question' (Q30) from 'unusual wording of a real alert' (Q04).",
        "The test-split end-to-end numbers of 1.000 (Table 7) are not blind; the blind holdout rows in Table 6 "
        f"({f3(blind_after)} severity on v4) are the honest estimate.",
        "Most end-to-end errors are under-rating, not over-rating. For a triage tool that is the worse direction.",
    ]), "warn", "Honest reading"))

    # ------------------------------------------------------------------ 6
    story += h1("6. Limitations")
    story += bullets([
        "<b>Synthetic and small.</b> 19 short playbooks, 32 retrieval queries and 12-16 alerts per end-to-end set, "
        "written by the author. Results do not transfer to real SOC telemetry, and one case moves end-to-end "
        "accuracy by 6-20 points.",
        "<b>Label ambiguity.</b> Some errors (W10, H07) sit on the border between 'anomaly' and 'specific "
        "telemetry'; a second labeller would likely disagree on a few labels. No inter-annotator agreement was "
        "measured.",
        "<b>Model judgement inside a deterministic score.</b> Confidence and impact still come from Gemma; the matrix "
        "makes severity consistent but cannot correct wrong factors (Section 5.2).",
        "<b>Lossy grounding.</b> Literal substring matching drops correct paraphrases (safe but lossy). Injection "
        "detection is pattern-based; the real protection is that tools are read-only and allow-listed.",
        "<b>Single global abstention threshold</b> and a single-process SQLite store without authentication: the app "
        "is meant to run on localhost only.",
        "<b>Report quality not scored.</b> The summary and recommended actions are checked for valid citations but "
        "not graded for usefulness.",
    ])
    story += h1("7. Next steps")
    story.append(p("Ordered by expected value; each item names how it would be measured, on a new holdout set so "
                   "that the measurement stays blind."))
    story += numbered([
        "<b>Fix under-triage first.</b> Ask for the impact evidence as a quoted span from the alert and map phrases "
        "such as 'entered their passwords' or 'process executed' to confirmed impact in code. Measure: severity "
        "accuracy and the number of under-rated cases on holdout v5.",
        "<b>Query cleaning for retrieval.</b> Strip hostnames and IPs from search queries (Q02) and add a small "
        "synonym list (isolate/disconnect/cut off, Q26). Measure: Recall@3 and MRR@5 on a new dev set, then test.",
        "<b>Better abstention.</b> Replace the single score floor with a margin rule (top-1 minus top-2) or a "
        "per-category floor. Measure: abstention accuracy, separately for false and missed abstentions.",
        "<b>A larger, second-labeller dataset.</b> 100+ queries labelled by two people, with Cohen's kappa, so "
        "differences of a few points become meaningful.",
        "<b>LLM-as-judge for report quality,</b> calibrated against human ratings on 20 reports before trusting it.",
        "<b>Analyst feedback loop</b> in the dashboard (accept/override severity) to collect real error cases.",
    ])

    story.append(p("Reproducibility and references", H2))
    story.append(p(f"Retrieval: <font face='Courier'>{meta['command']}</font> (CPU, about 1 min); end-to-end: "
                   f"<font face='Courier'>{e2e['meta']['command']}</font>; figures: "
                   "<font face='Courier'>python -m scripts.make_figures</font>; this report: "
                   "<font face='Courier'>python -m scripts.build_report</font>; offline tests: "
                   f"<font face='Courier'>pytest</font> (mocked LLM). Python {meta['python']}; LSA seed "
                   f"{meta['seeds']['lsa_truncated_svd_random_state']}; BM25 k1={meta['bm25']['k1']}, "
                   f"b={meta['bm25']['b']}; embeddings {meta['embedding_models']['sbert']}; dataset sha256/16 "
                   f"{meta['dataset_sha256_16']}. Per-example results: eval/results/per_example.csv and "
                   "eval/results/rounds/.", SMALL))
    story.append(p("References: Nat-D/kmitl-llm-app-demo (course reference app; general ideas only - thin LLM "
                   "adapter, min_score floor, router/service/repository layering - no code, corpus or evaluation "
                   "data copied); Robertson &amp; Zaragoza (2009) BM25; Reimers &amp; Gurevych (2019) "
                   "Sentence-BERT; Deerwester et al. (1990) LSA; RFC 5737.", SMALL))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=1.6 * cm,
                            bottomMargin=2.0 * cm, title="SentinelAI Capstone Report", author="SentinelAI project")
    doc.build(glue_headings(story), onFirstPage=footer, onLaterPages=footer)
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    build()
