"""Build the Thai version of the capstone report.

python -m scripts.build_report_th  ->  docs/report/SentinelAI_Capstone_Report_TH.pdf

All numbers are read from eval/results/ at build time, exactly like scripts/build_report.py.
The page is rendered as HTML and printed by a headless Chromium browser (Edge or Chrome), because
ReportLab cannot shape Thai (stacked vowels/tone marks) or break Thai lines at word boundaries.

Font: LINE Seed Sans TH (SIL Open Font License). It is not committed; point SENTINEL_THAI_FONT_DIR at the
folder holding LINESeedSansTH_Rg.ttf / LINESeedSansTH_Bd.ttf (default: ~/Downloads/LINE_Seed_Sans_TH).
The browser binary can be set with SENTINEL_BROWSER.
"""

from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
OUT = ROOT / "docs" / "report" / "SentinelAI_Capstone_Report_TH.pdf"
FONT_DIR = Path(os.environ.get("SENTINEL_THAI_FONT_DIR", Path.home() / "Downloads" / "LINE_Seed_Sans_TH"))
BROWSERS = [os.environ.get("SENTINEL_BROWSER", ""),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "/usr/bin/chromium", "/usr/bin/google-chrome"]

ROUND_TH = {
    "r1_factor_rubric": "นิยาม confidence/impact ชัดเจนใน prompt; ค้นหาคู่มือหลักฐานไม่พอเมื่อ undetermined",
    "r2_evidence_kind_fallback": "จัดประเภทหลักฐาน → confidence แบบกำหนดแน่นอน; ค้นซ้ำเมื่อ agent ค้นไม่พบ",
    "r3_outcome_flag_label_fallback": "คำถามใช่/ไม่ใช่ “ผลการโจมตียืนยันแล้วหรือไม่”; ค้นด้วยชื่อประเภทเป็นทางสุดท้าย",
}
BLIND = [("r1_factor_rubric", "r0_baseline", "holdout v2 (16)"),
         ("r2_evidence_kind_fallback", "r1_factor_rubric", "holdout v3 (16)"),
         ("r3_outcome_flag_label_fallback", "r2_evidence_kind_fallback", "holdout v4 (16)")]
FAIL_CAUSE_TH = {
    "Q02": "ชื่อโฮสต์ LAB-TEST-07 ไปตรงกับแค็ตตาล็อกทรัพย์สิน (PB-018) จึงแซง PB-004",
    "Q04": "ไม่มีคำซ้ำกัน (ชื่อเมือง) และคะแนน dense ต่ำ จึงงดตอบผิดพลาด",
    "Q20": "เอกสารเกี่ยวข้องตัวที่สอง (PB-005) อยู่ต่ำกว่าอันดับ 3",
    "Q26": "คำศัพท์ไม่ตรงกัน: “cut off the network” กับ “isolate”",
    "Q30": "คำทั่วไปทางธุรกิจได้คะแนนสูงกว่าเกณฑ์งดตอบเล็กน้อย",
}
SCENARIO_TH = {"answerable": "ตอบได้", "ambiguous": "กำกวม", "similar_different_playbook": "คล้ายแต่คนละ playbook",
               "insufficient_evidence": "หลักฐานไม่พอ", "out_of_domain": "นอกขอบเขต", "false_positive": "false positive",
               "policy_question": "คำถามนโยบาย"}
METRIC_TH = {"valid_structured_output_rate": "ผลลัพธ์ผ่าน schema", "incident_type_accuracy": "ประเภทเหตุการณ์ถูก",
             "severity_accuracy": "ระดับความรุนแรงถูก", "citation_validity_rate": "อ้างอิงเฉพาะเอกสารที่ค้นได้",
             "relevant_citation_rate": "อ้างอิง playbook ที่เกี่ยวข้อง",
             "undetermined_flagged_rate": "เคส undetermined ส่งให้คนตรวจ",
             "native_tool_mode_rate": "ใช้ native tool calling"}


def f3(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def esc(x) -> str:
    return html.escape(str(x))


def table(rows: list[list], cls: str = "", highlight: int | None = None) -> str:
    head = "".join(f"<th>{esc(c)}</th>" for c in rows[0])
    body = "".join(
        f"<tr{' class=hl' if i == highlight else ''}>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>"
        for i, r in enumerate(rows[1:], start=1))
    return f"<table class='{cls}'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def find_browser() -> str:
    for b in BROWSERS:
        if b and Path(b).is_file():
            return b
    sys.exit("No Edge/Chrome found; set SENTINEL_BROWSER to a Chromium-based browser executable.")


def build_html() -> str:
    regular, bold = FONT_DIR / "LINESeedSansTH_Rg.ttf", FONT_DIR / "LINESeedSansTH_Bd.ttf"
    if not regular.is_file() or not bold.is_file():
        sys.exit(f"LINE Seed Sans TH not found in {FONT_DIR}; set SENTINEL_THAI_FONT_DIR.")
    summary = json.loads((RES / "retrieval_summary.json").read_text(encoding="utf-8"))
    runs = json.loads((RES / "retrieval_runs.json").read_text(encoding="utf-8"))["runs"]
    e2e = json.loads((RES / "e2e_summary.json").read_text(encoding="utf-8"))
    r0 = json.loads((RES / "rounds" / "r0_baseline" / "e2e_summary.json").read_text(encoding="utf-8"))
    rounds = json.loads((RES / "rounds" / "rounds_summary.json").read_text(encoding="utf-8"))
    proxy_path = RES / "proxy_compat.json"
    proxy = json.loads(proxy_path.read_text(encoding="utf-8")) if proxy_path.is_file() else {}
    meta, base, sel = summary["meta"], summary["baseline"], summary["selected"]
    paired, counts = summary["test_paired_rr@5_vs_baseline"], meta["dataset_counts"]
    scen: dict[str, int] = {}
    for line in (ROOT / meta["dataset"]).read_text(encoding="utf-8").splitlines():
        if line.strip():
            s = json.loads(line)["scenario"]
            scen[s] = scen.get(s, 0) + 1
    agg = e2e["aggregate"]
    mk = ["recall@3", "mrr@5", "precision@3", "hit@1", "abstention_accuracy"]

    t1 = table([["ชุดทดสอบ (test)", "Recall@3", "MRR@5", "P@3", "Hit@1", "งดตอบถูก"],
                [f"A: {base['name']}"] + [f3(base["test"][k]) for k in mk],
                [f"B: {sel['name']} (เลือกจาก dev)"] + [f3(sel["test"][k]) for k in mk]], "num", highlight=2)
    rows2 = [["Configuration", "chunks", "dev R@3", "dev MRR@5", "dev งดตอบ", "test R@3", "test MRR@5", "test งดตอบ"]]
    hl = None
    for i, r in enumerate(runs, start=1):
        hl = i if r["name"] == sel["name"] else hl
        rows2.append([r["name"], r["n_chunks"], f3(r["dev"]["recall@3"]), f3(r["dev"]["mrr@5"]),
                      f3(r["dev"]["abstention_accuracy"]), f3(r["test"]["recall@3"]), f3(r["test"]["mrr@5"]),
                      f3(r["test"]["abstention_accuracy"])])
    t2 = table(rows2, "num small", highlight=hl)
    rows3 = [["คำถาม", "สถานการณ์", "เอกสารที่ถูก", "Top-5 ที่ได้", "สาเหตุ (วิเคราะห์เอง)"]]
    for f in summary["selected_test_failures"]:
        rows3.append([f["id"], SCENARIO_TH.get(f["scenario"], f["scenario"]), f["relevant"] or "ไม่มี (ควรงดตอบ)",
                      f["ranked_top5"].replace("|", ", "), FAIL_CAUSE_TH.get(f["id"], "ดู per_example.csv")])
    t3 = table(rows3, "small")
    rows4 = [["รอบ", "สิ่งที่เปลี่ยน", "ชุดที่ไม่เคยเห็น", "Severity", "อ้างอิงที่เกี่ยวข้อง"]]
    for new, old, ds in BLIND:
        a, b = rounds.get(old, {}).get(ds), rounds.get(new, {}).get(ds)
        if a and b:
            rows4.append([new.split("_")[0], ROUND_TH[new], ds,
                          f"{f3(a['severity_accuracy'])} → {f3(b['severity_accuracy'])}",
                          f"{f3(a['relevant_citation_rate'])} → {f3(b['relevant_citation_rate'])}"])
    t4 = table(rows4, "small")
    rows5 = [["ตัวชี้วัด (ชุด test)", "r0", "ฉบับสุดท้าย"]]
    for k, v in agg.items():
        if k in METRIC_TH:
            rows5.append([METRIC_TH[k], f3(r0["aggregate"][k]), f3(v)])
    t5 = table(rows5, "num narrow")
    proxy_txt = ", ".join(f"{k}={'ผ่าน' if v.get('ok') else 'ไม่ผ่าน'}" for k, v in proxy.items()
                          if isinstance(v, dict)) or "ยังไม่ได้ตรวจ"
    scen_txt = ", ".join(f"{SCENARIO_TH.get(k, k)} {v}" for k, v in sorted(scen.items()))
    arch = (ROOT / "docs/architecture/architecture.png").as_uri()
    fig = (ROOT / "docs/report/figures/retrieval_comparison.png").as_uri()

    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><title>รายงานโครงงาน SentinelAI</title>
<style>
@font-face {{ font-family: "LINE Seed Sans TH"; src: url("{regular.as_uri()}"); font-weight: 400; }}
@font-face {{ font-family: "LINE Seed Sans TH"; src: url("{bold.as_uri()}"); font-weight: 700; }}
@page {{ size: A4; margin: 17mm 18mm 18mm 18mm;
  @bottom-left {{ content: "SentinelAI – รายงานโครงงาน (ข้อมูลสังเคราะห์)"; font: 7.5pt "LINE Seed Sans TH"; color: #666; }}
  @bottom-right {{ content: "หน้า " counter(page); font: 7.5pt "LINE Seed Sans TH"; color: #666; }} }}
body {{ font-family: "LINE Seed Sans TH", sans-serif; font-size: 9.6pt; line-height: 1.55; color: #1b1f24; margin: 0; }}
h1 {{ font-size: 18pt; text-align: center; margin: 10mm 0 2mm; color: #123a5a; line-height: 1.3; }}
.sub {{ text-align: center; margin: 0; }} .meta {{ text-align: center; font-size: 7.8pt; color: #555; margin: 1mm 0 5mm; }}
h2 {{ font-size: 12.5pt; color: #123a5a; margin: 5mm 0 1.5mm; break-after: avoid; }}
h3 {{ font-size: 10.5pt; margin: 3mm 0 1mm; break-after: avoid; }}
p {{ margin: 0 0 2mm; text-align: justify; text-justify: inter-character; }}
ul {{ margin: 0 0 2mm; padding-left: 5mm; }} li {{ margin-bottom: 0.8mm; }}
table {{ border-collapse: collapse; width: 100%; margin: 1mm 0 2mm; font-size: 8pt; line-height: 1.35; break-inside: avoid; }}
table.small {{ font-size: 7.4pt; }} table.narrow {{ width: 70%; }}
th {{ background: #123a5a; color: #fff; text-align: left; padding: 1.2mm 1.5mm; font-weight: 700; }}
td {{ border: 0.3mm solid #b8c4d0; padding: 1mm 1.5mm; vertical-align: top; }}
tbody tr:nth-child(even) td {{ background: #f3f6f9; }} tr.hl td {{ background: #dcecf8 !important; }}
table.num td + td {{ font-variant-numeric: tabular-nums; }}
.cap {{ font-size: 7.8pt; color: #444; margin: 2mm 0 0.5mm; break-after: avoid; }}
figure {{ margin: 2mm 0; break-inside: avoid; text-align: center; }} figure img {{ max-width: 100%; }}
figcaption {{ font-size: 7.8pt; color: #444; }}
code {{ font-family: Consolas, monospace; font-size: 8.4pt; }}
.note {{ font-size: 7.8pt; color: #444; }}
</style></head><body>

<h1>SentinelAI: ผู้ช่วยคัดกรองเหตุการณ์ความปลอดภัยอัจฉริยะสำหรับ SOC</h1>
<p class="sub">รายงานโครงงานรายวิชาการพัฒนาแอปพลิเคชันด้วย LLM (ฉบับภาษาไทย)</p>
<p class="meta">โมเดล gemma-4-E4B-it ผ่าน OpenAI-compatible proxy ของรายวิชา · ผล retrieval สร้างเมื่อ
{esc(meta['generated_at'][:10])} · ผล end-to-end ล่าสุด {esc(e2e['meta']['generated_at'][:10])} ·
ชุดข้อมูล {esc(meta['dataset'])} (sha256/16 {esc(meta['dataset_sha256_16'])})</p>

<h2>บทคัดย่อ</h2>
<p>SentinelAI ช่วยนักวิเคราะห์ Security Operations Center (SOC) ระดับเริ่มต้นคัดกรอง alert ความปลอดภัยแบบสังเคราะห์
โดยรวม structured extraction ที่ตรวจด้วย schema และการตรวจ grounding แบบตรงตัวอักษร, retrieval-augmented generation
บน playbook สมมติที่เขียนขึ้นเอง 19 ฉบับ, agent ที่เรียกใช้เครื่องมืออ่านอย่างเดียว 3 ตัวภายใต้ขอบเขตที่กำหนด,
ตารางคำนวณความรุนแรงแบบกำหนดแน่นอน และรายงานเหตุการณ์ที่ตรวจการอ้างอิงแล้ว ให้บริการผ่าน FastAPI และ web dashboard
บนชุด test ที่แยกไว้ {counts['test']} คำถาม (ตอบได้ {counts['test_answerable']} ข้อ) ค่าที่เลือกจากชุด dev
({esc(sel['name'])}) เพิ่ม Recall@3 จาก {f3(base['test']['recall@3'])} เป็น {f3(sel['test']['recall@3'])} และ MRR@5 จาก
{f3(base['test']['mrr@5'])} เป็น {f3(sel['test']['mrr@5'])} เทียบกับ baseline BM25 แบบ chunk คงที่ ซึ่งเป็นการปรับปรุงเล็กน้อยบนชุดทดสอบขนาดเล็ก
สำหรับการประเมินแบบ end-to-end กับ Gemma จริง ระบบถูกปรับปรุง 3 รอบ โดยแต่ละรอบวัดผลบนชุด holdout ใหม่ที่เขียนไว้ก่อนแก้ (หัวข้อ 7)</p>

<h2>1. ที่มาและปัญหา</h2>
<p>นักวิเคราะห์ระดับ Tier-1 ต้องรับมือกับ alert จำนวนมากในหลายรูปแบบ ข้อผิดพลาดที่พบบ่อยของผู้เริ่มต้นคือ
(ก) สับสน alert ที่ดูคล้ายกันแต่ต้องใช้ playbook ต่างกัน เช่น การเดารหัสผ่านจำนวนมากกับการ login สำเร็จหลังจากนั้น
(ข) เติมข้อมูลที่ขาดด้วยการเดา และ (ค) ให้ระดับความรุนแรงไม่สม่ำเสมอ เครื่องมือแชตกับเอกสารทั่วไปมักทำให้ข้อ (ข) และ (ค)
แย่ลง เพราะโมเดลภาษาสามารถสร้างชื่อโฮสต์ การอ้างอิง และลำดับความสำคัญขึ้นมาเองอย่างมั่นใจ SentinelAI จึงออกแบบตามหลักตรงข้าม:
ให้โมเดลจัดการเรื่องภาษา ส่วนทุกอย่างที่ต้องทำซ้ำได้หรือตรวจสอบได้ให้โค้ดเป็นผู้ทำและตรวจเทียบกับหลักฐาน</p>

<h2>2. กลุ่มผู้ใช้และวัตถุประสงค์</h2>
<ul>
<li><b>ผู้ใช้:</b> นักวิเคราะห์ SOC ระดับเริ่มต้นและนักศึกษาที่เรียนการคัดกรองเหตุการณ์ รวมถึงผู้สอนที่ตรวจขั้นตอนการทำงาน</li>
<li><b>O1</b> ดึงข้อมูลเหตุการณ์แบบมีโครงสร้างโดยไม่สร้างค่าขึ้นเอง (Pydantic + การตรวจ grounding)</li>
<li><b>O2</b> ค้นหา playbook ที่ถูกต้องและอ้างอิงเฉพาะเอกสารที่ค้นได้จริง (RAG + การตรวจการอ้างอิง)</li>
<li><b>O3</b> ให้ agent เลือกเครื่องมือสืบสวนได้อย่างปลอดภัย (allow-list, schema, เงื่อนไขหยุดที่ชัดเจน)</li>
<li><b>O4</b> คำนวณความรุนแรงแบบกำหนดแน่นอนจากนโยบายที่มีเอกสาร (PB-002) และแค็ตตาล็อกทรัพย์สิน</li>
<li><b>O5</b> วัดคุณภาพ retrieval เทียบ baseline ด้วยโปรโตคอล dev/test และรายงานตามจริง</li>
</ul>

<h2>3. สถาปัตยกรรมระบบและการไหลของข้อมูล</h2>
<figure><img src="{arch}" style="width:84%"><figcaption>ภาพที่ 1 ชั้นของระบบและลำดับการทำงานของคำขอ
กล่องสีเขียวคือส่วนประกอบด้านความปลอดภัยที่ทำงานแบบกำหนดแน่นอน</figcaption></figure>
<p>Router ทำหน้าที่เพียงตรวจ input ของ HTTP และแปลงข้อผิดพลาด (422 input ไม่ถูกต้อง, 400 รหัสเอกสารผิดรูปแบบ,
502 ผลลัพธ์โมเดลไม่ผ่านการตรวจ, 503 ยังไม่ได้ตั้งค่า proxy) <i>AnalysisService</i> ควบคุมลำดับงานทั้งหมด ได้แก่
extraction, grounding, agent loop, การบังคับเรียกเครื่องมือ, การร่างรายงาน และการบันทึกผล Repository ห่อ SQLite
(ผลวิเคราะห์ที่บันทึกและประวัติเหตุการณ์สังเคราะห์ ใช้ parameterised SQL เท่านั้น) และแค็ตตาล็อกทรัพย์สิน JSON
มี LLM adapter เพียงตัวเดียวที่สื่อสารกับโมเดล ทำให้ทดสอบทั้ง pipeline ได้ด้วย client ปลอมที่กำหนดคำตอบไว้ล่วงหน้า</p>

<h2>4. การเชื่อมต่อ LLM, RAG, Structured Output และการออกแบบ Agent</h2>
<p><b>การเชื่อมต่อ LLM</b> ใช้ OpenAI Python SDK ทางการ ชี้ไปที่ proxy ของรายวิชาด้วย OPENAI_API_KEY และ OPENAI_BASE_URL
จาก environment ใช้โมเดล gemma-4-E4B-it ที่ temperature 0 ขอ JSON mode และตัดออกอัตโนมัติหาก proxy ไม่รองรับ
ผลการตรวจความเข้ากันได้ของ proxy: {esc(proxy_txt)}</p>
<p><b>Structured output</b> ผลการดึงข้อมูลและร่างรายงานถูกตรวจด้วย Pydantic (ประเภทเหตุการณ์แบบ enum, ตรวจ IP,
จำกัดขนาด list) หากไม่ผ่านจะส่งข้อความผิดพลาดกลับให้โมเดลแก้ สูงสุด 3 ครั้ง ถ้ายังไม่ผ่าน API จะตอบ 502 พร้อมระบุขั้นตอนที่ล้มเหลว
แทนการสร้างรายงานปลอม หลังผ่านการตรวจ ค่าทุกค่าที่ดึงได้ (ชื่อโฮสต์, IP, ผู้ใช้, เวลา, หลักฐาน, indicator)
ต้องปรากฏตรงตัวใน alert มิฉะนั้นจะถูกลบและระบุเป็นข้อจำกัด
ความน่าเชื่อถือของ alert ไม่ได้ให้โมเดลเลือกระดับเองโดยตรง แต่ให้จัดประเภทหลักฐาน (specific telemetry / anomaly / vague)
แล้วโค้ดแปลงเป็นระดับ confidence แบบกำหนดแน่นอน (ดูหัวข้อ 7)</p>
<p><b>RAG</b> playbook แต่ละฉบับมีรหัสคงที่ (PB-001..PB-019) ชื่อ เวอร์ชัน หมวดหมู่ และแหล่งที่มา และระบุชัดว่าเป็นเอกสารสมมติ
เอกสารถูกทำความสะอาด (ไม่ index ข้อความประกาศที่ซ้ำกัน) และแบ่งตามหัวข้อ markdown โดยเติมชื่อเอกสารและหัวข้อไว้ด้านหน้า
การค้นหาให้คะแนน chunk ด้วย BM25 และ cosine similarity ของ all-MiniLM-L6-v2 แล้วรวมเป็น
alpha·cos + (1−alpha)·bm25/(bm25+8) จัดอันดับเอกสารตาม chunk ที่ดีที่สุด และงดตอบเมื่อคะแนนสูงสุดต่ำกว่าเกณฑ์ที่ปรับจากชุด dev
รายงานอ้างอิงได้เฉพาะรหัสที่ค้นได้จริง หากผิดจะสั่งแก้ และหากยังผิดจะคืนข้อผิดพลาด</p>
<p><b>Agent</b> มีเครื่องมือ search_playbooks, calculate_severity และ lookup_incident_history ทั้งหมดอ่านอย่างเดียว
แต่ละตัวมี Pydantic argument model (ห้าม field เกิน, จำกัดค่าจำนวนเต็ม, regex ชื่อโฮสต์) ใช้ native OpenAI tool calling
เมื่อรองรับ มิฉะนั้นใช้ JSON action protocol ที่มีเอกสารและระบุไว้ใน trace loop หยุดเมื่อได้คำตอบสุดท้าย, ครบ 6 ครั้ง,
เกิน 150 วินาที, ผิดพลาดติดกัน 3 ครั้ง หรือการเชื่อมต่อล้มเหลว และปฏิเสธการเรียกซ้ำ หาก agent ข้ามการค้นหา
ค้นแล้วไม่พบอะไร หรือคำนวณความรุนแรงด้วยปัจจัยที่ต่างจาก extraction orchestrator จะเรียกเครื่องมือเองและบันทึกเป็นขั้น enforced
ข้อความ alert, ข้อความจาก playbook และผลจากเครื่องมือถูกครอบด้วย data tag และถือเป็นข้อมูลที่ไม่น่าเชื่อถือ</p>
<p><b>ความรุนแรง</b> score = tier(1–4) + confidence(1–3) + 2×impact(0–3) + 2 หากเป็นบัญชีสิทธิ์สูง
ช่วงคะแนน 0–4 Informational, 5–6 Low, 7–8 Medium, 9–10 High, 11 ขึ้นไป Critical ค่า tier มาจากแค็ตตาล็อกเสมอ
ไม่ได้มาจากโมเดล ทรัพย์สินที่ไม่รู้จักใช้ค่า medium และถูกแจ้งให้ตรวจ</p>

<h2>5. การสร้างชุดข้อมูลและวิธีการ</h2>
<p>ชุดประเมิน retrieval มีคำถามที่เขียนเอง {counts['total']} ข้อ (dev {counts['dev']}, test {counts['test']})
แต่ละข้อมีรหัสเอกสารที่เกี่ยวข้อง ประเภทเหตุการณ์ที่คาดหวัง ระดับความรุนแรงที่คาดหวังพร้อมปัจจัย (เมื่อระบุได้)
การงดตอบที่คาดหวัง และหมายเหตุอธิบาย label สัดส่วนสถานการณ์: {esc(scen_txt)}
การตรวจอัตโนมัติยืนยันว่ารหัสเอกสารมีอยู่จริง, label ความรุนแรงตรงกับสูตร PB-002 และไม่มีคำถามใดใช้ข้อความ 6 คำติดกันซ้ำกับ corpus
สำหรับการประเมิน end-to-end มีชุด holdout เพิ่มอีก 3 ชุด (v2, v3, v4 ชุดละ 16 alert) ซึ่งเขียนและใส่ label ก่อนการปรับปรุงแต่ละรอบ
ข้อมูลทั้งหมดเป็นข้อมูลสังเคราะห์ IP มาจากช่วงสำหรับเอกสาร RFC 5737</p>

<h2>6. ตัวชี้วัดและ baseline</h2>
<ul>
<li>Recall@3 = จำนวนเอกสารเกี่ยวข้องใน 3 อันดับแรก / จำนวนเอกสารเกี่ยวข้อง; MRR@5 = 1/อันดับของเอกสารเกี่ยวข้องตัวแรกใน 5 อันดับแรก
(ถ้าไม่มีเป็น 0); Precision@3 และ Hit@1 เป็นตัวชี้วัดรอง ทั้งหมดเฉลี่ยเฉพาะคำถามที่<b>ตอบได้</b></li>
<li>ความถูกต้องของการงดตอบคิดจาก<b>ทุก</b>คำถาม: ถูกเมื่อระบบงดตอบในกรณีที่ไม่มีเอกสารเกี่ยวข้องเท่านั้น</li>
<li><b>Baseline A</b>: BM25 บน chunk คงที่ 120 คำ ซึ่งเป็นการทำแบบตรงไปตรงมาครั้งแรก</li>
<li><b>ตัวเลือกที่ทดลอง</b>: BM25 แบ่งตามหัวข้อ; dense LSA (TF-IDF + SVD, seed 42); dense MiniLM; hybrid ที่ alpha ∈ {{0.3, 0.5, 0.7}}</li>
<li><b>โปรโตคอล</b>: ปรับเกณฑ์บน dev เท่านั้น และกำหนดกฎการเลือกไว้ล่วงหน้า: {esc(meta['selection_rule'])}
รายงานผล test ครั้งเดียวสำหรับ baseline และค่าที่เลือก (ค่าอื่นแสดงเพื่อความโปร่งใสแต่ไม่ได้ใช้ตัดสินใจ)</li>
<li><b>End-to-end</b>: ผลลัพธ์ผ่าน schema, ประเภทเหตุการณ์ถูก, ความรุนแรงถูก, อ้างอิงเฉพาะเอกสารที่ค้นได้,
อ้างอิง playbook ที่เกี่ยวข้อง และการส่งเคส undetermined ให้คนตรวจ</li>
</ul>

<h2>7. ผลการทดลอง</h2>
<h3>Retrieval</h3>
<p class="cap">ตารางที่ 1 baseline เทียบกับค่าที่เลือกบนชุด test ({counts['test']} คำถาม, ตอบได้ {counts['test_answerable']} ข้อ)</p>
{t1}
<p>เทียบ reciprocal rank รายคำถามบน test กับ baseline: ชนะ {paired['wins']} แพ้ {paired['losses']} เสมอ {paired['ties']}
บนชุด dev ค่าที่เลือกได้ Recall@3 {f3(sel['dev']['recall@3'])} / MRR@5 {f3(sel['dev']['mrr@5'])} เทียบกับ
{f3(base['dev']['recall@3'])} / {f3(base['dev']['mrr@5'])} ของ baseline</p>
<p class="cap">ตารางที่ 2 ทุก configuration (การเลือกใช้เฉพาะคอลัมน์ dev)</p>
{t2}
<figure><img src="{fig}"><figcaption>ภาพที่ 2 Recall@3 และ MRR@5 ของแต่ละ configuration บน dev และ test
(สร้างจาก eval/results/retrieval_runs.json)</figcaption></figure>

<h3>การประเมิน end-to-end กับ Gemma</h3>
<p>ทุก alert ที่มี label ถูกส่งผ่าน pipeline จริงทั้งหมด การรันครั้งแรก (r0) พบว่า Gemma ให้ alert confidence เป็น “medium”
เกือบทุกเคส และประเมิน impact ต่ำกว่าความจริง จึงปรับปรุง 3 รอบ (บันทึกใน docs/EXPERIMENT_LOG.md)
ก่อนแต่ละรอบได้เขียนชุด holdout ใหม่ 16 alert พร้อม label ทำให้ทุกการเปลี่ยนแปลงมีการวัดผลบนข้อมูลที่ไม่ได้ใช้ออกแบบอย่างน้อยหนึ่งชุด
(ตารางที่ 4) ส่วนชุด test เดิมถูกดูเคสที่ผิดหลัง r0 แล้ว จึงไม่ใช่การวัดแบบ blind อีกต่อไป</p>
<p class="cap">ตารางที่ 4 แต่ละรอบวัดผลบนชุด holdout ที่เขียนไว้ก่อนรอบนั้น (ก่อน → หลัง)</p>
{t4}
<p class="cap">ตารางที่ 5 ชุด test ({agg['cases_run']} alert, มี label ความรุนแรง {agg['severity_cases']} ข้อ)
รันครั้งแรกเทียบกับฉบับสุดท้าย (ไม่ใช่ blind หลัง r0)</p>
{t5}
<p class="note">รันครั้งสุดท้าย {esc(e2e['meta']['generated_at'])} ({esc(e2e['meta'].get('round') or '-')})
การรัน r2 ซ้ำได้ระดับความรุนแรงและประเภทเหตุการณ์เหมือนเดิมทุกเคส ความต่างระหว่างรอบจึงไม่ใช่ความแปรปรวนจากการสุ่ม
r3 พลาดเพิ่ม 1 เคสความรุนแรงและ 1 การอ้างอิงบน holdout v3 (ชุดที่เคยเห็นแล้ว) แต่เมื่อรวมทุกชุด
จำนวนความรุนแรงที่ถูกเพิ่มจาก 40/51 เป็น 43/51</p>

<h2>8. กรณีที่สำเร็จและการวิเคราะห์ความผิดพลาด</h2>
<p><b>กรณีที่สำเร็จ</b> การแบ่ง chunk ตามหัวข้อเพียงอย่างเดียวเพิ่ม Recall@3 ของ BM25 บน test จาก
{f3(runs[0]['test']['recall@3'])} เป็น {f3(runs[1]['test']['recall@3'])} เพราะชื่อหัวข้ออย่าง “Recognising the pattern”
และ “Indicators” รวมคำที่แยกแยะได้ไว้ด้วยกัน hybrid ดึงขั้นตอนสำหรับหลักฐานไม่พอของ alert ที่คลุมเครือ (Q24) ได้
ซึ่ง baseline จัดไว้อันดับที่สี่ การทดสอบ pipeline ด้วย LLM จำลองแสดงว่าการอ้างอิงที่แต่งขึ้นถูกแก้หรือปฏิเสธ
ชื่อโฮสต์ที่แต่งขึ้นถูกลบ และคำขอ “run_shell” ที่ถูกแทรกมาถูกปฏิเสธ</p>
<p class="cap">ตารางที่ 3 ความผิดพลาดที่เหลือของ retrieval configuration ที่เลือกบนชุด test</p>
{t3}
<p><b>ข้อสังเกตตามจริง</b> (1) ตัวชี้วัดลดลงจาก dev ไป test ทุก configuration แสดงว่าชุด dev ง่ายกว่า
และด้วยคำถามที่ตอบได้เพียง 14 ข้อ คำถามเดียวเปลี่ยน Recall@3 ได้ประมาณ 0.07
(2) dense-sbert-fixed ดีที่สุดบน test แต่ไม่ได้ถูกเลือก เพราะการเลือกตอนนี้เท่ากับการจูนกับชุด test
(3) end-to-end ที่ยังพลาด: impact ของการโจมตีที่ยืนยันแล้วบางเคสยังเป็น “suspected” และการจัดประเภทหลักฐานไม่คงที่ในเคสก้ำกึ่ง
(4) เคสที่ตั้งใจให้กำกวมบางเคสถูกจัดเป็น undetermined ซึ่งปลอดภัยเพราะถูกส่งให้คนตรวจเสมอ</p>

<h2>9. ความปลอดภัย</h2>
<ul>
<li>ไม่มีเครื่องมือ shell, ระบบไฟล์, การสแกนเครือข่าย หรือการเขียนข้อมูล ชื่อเครื่องมือต้องอยู่ใน allow-list และ argument ถูกตรวจด้วย schema
(มีการทดสอบ path traversal และ SQL injection)</li>
<li>Prompt injection: เนื้อหาที่ไม่น่าเชื่อถือถูกระบุเป็นข้อมูล วลีที่เป็นการแทรกคำสั่งถูกตรวจจับและบังคับให้คนตรวจ
และข้อจำกัดเชิงสถาปัตยกรรมทำให้การใช้เครื่องมือผิดวัตถุประสงค์ไม่เกิดผลเสีย</li>
<li>การอ้างอิงต้องเป็นรหัสที่ค้นได้จริง ความรุนแรงคำนวณด้วยโค้ด และค่าที่ไม่มีในหลักฐานถูกลบ</li>
<li>Secret มาจาก environment variable เท่านั้น (.env ถูก git-ignore) ไม่ถูก log หรือส่งกลับ ข้อความผิดพลาดถูก redact
จำกัดขนาด request 64 KiB (413) และวิเคราะห์พร้อมกันได้สูงสุด 2 งาน (429) ใช้ CSP เข้มงวดและแสดงผลด้วย textContent</li>
</ul>

<h2>10. ข้อจำกัดและงานในอนาคต</h2>
<ul>
<li>corpus และชุดข้อมูลเป็นข้อมูลสังเคราะห์ขนาดเล็ก ผลลัพธ์ไม่สามารถใช้แทนข้อมูล SOC จริงได้</li>
<li>ชุด end-to-end มีขนาดเล็ก (12–16 alert) หนึ่งเคสเปลี่ยนความแม่นยำได้ 6–20 จุด</li>
<li>grounding แบบตรงตัวอักษรตัดค่าที่ถูกแต่เขียนต่างออกไป และการตรวจ injection แบบ pattern อาจถูกเลี่ยงได้</li>
<li>ใช้เกณฑ์งดตอบค่าเดียว ไม่มีระบบยืนยันตัวตนหรือแยกผู้ใช้หลายคน จึงควรรันในเครื่องเท่านั้น</li>
<li>อนาคต: เชื่อมโยงหลาย alert, รับ feedback จากนักวิเคราะห์, ชุดประเมินที่ใหญ่ขึ้น, การเขียน query ใหม่,
และใช้ LLM-as-judge ประเมินคุณภาพรายงานโดยเทียบกับมนุษย์</li>
</ul>
<h3>การทำซ้ำผลลัพธ์</h3>
<p class="note">คำสั่ง: <code>{esc(meta['command'])}</code>, <code>{esc(e2e['meta']['command'])}</code>,
<code>python -m eval.compare_rounds</code>; python {esc(meta['python'])}; LSA seed
{meta['seeds']['lsa_truncated_svd_random_state']}; BM25 k1={meta['bm25']['k1']}, b={meta['bm25']['b']};
embedding model {esc(meta['embedding_models']['sbert'])} ผลรายข้ออยู่ใน eval/results/per_example.csv และ eval/results/rounds/
การทดสอบ: <code>pytest</code> (offline, LLM จำลอง)</p>
<p class="note">อ้างอิง: Nat-D/kmitl-llm-app-demo (แหล่งอ้างอิงของรายวิชา ใช้เป็นแนวคิดเท่านั้น); Robertson &amp; Zaragoza (2009) BM25;
Reimers &amp; Gurevych (2019) Sentence-BERT; Deerwester et al. (1990) LSA; RFC 5737; ฟอนต์ LINE Seed Sans TH (SIL OFL 1.1)</p>
</body></html>"""


def build() -> None:
    browser = find_browser()
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "report_th.html"
        page.write_text(build_html(), encoding="utf-8")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        # argument list, no shell; the binary comes from the fixed list above or SENTINEL_BROWSER
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",  # noqa: S603
                        "--allow-file-access-from-files", f"--user-data-dir={Path(tmp) / 'profile'}",
                        f"--print-to-pdf={OUT}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
    if not OUT.is_file():
        sys.exit("browser did not produce a PDF")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    build()
