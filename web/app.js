// SentinelAI dashboard. All dynamic text is inserted with textContent (no innerHTML of data).
"use strict";

const $ = (sel) => document.querySelector(sel);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

const INCIDENT_TYPES = ["brute_force", "suspicious_login", "privileged_account_compromise", "malware",
  "suspicious_powershell", "command_injection", "unusual_outbound", "data_exfiltration", "suspicious_dns",
  "phishing", "false_positive", "undetermined"];

/* ---------------- tabs ---------------- */
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
  document.querySelectorAll(".view").forEach((v) => { v.hidden = v.id !== `view-${name}`; });
  if (name === "history") { loadAnalyses(); loadHistory(); }
  if (name === "evaluation") loadEvaluation();
}

/* ---------------- status ---------------- */
async function loadHealth() {
  try {
    const h = await api("/api/health");
    const llm = $("#status-llm");
    llm.textContent = h.llm_configured ? `LLM: ${h.model}` : "LLM: not configured";
    llm.className = `pill ${h.llm_configured ? "ok" : "warn"}`;
    llm.title = h.llm_configured ? "Class proxy configured" : "Set OPENAI_API_KEY and OPENAI_BASE_URL to enable analysis";
    const r = h.retrieval;
    const name = r.method === "bm25" ? `bm25 · ${r.chunking}` : `${r.method} · ${r.dense_backend} · α=${r.hybrid_alpha}`;
    $("#status-retrieval").textContent = `RAG: ${name}${r.fallback ? " (fallback)" : ""} · ${h.documents} docs`;
  } catch {
    $("#status-llm").textContent = "API unreachable";
    $("#status-llm").className = "pill warn";
  }
}

/* ---------------- samples ---------------- */
let SAMPLES = [];
async function loadSamples() {
  SAMPLES = await api("/api/samples");
  const sel = $("#sample-select");
  for (const s of SAMPLES) sel.append(el("option", { value: s.id, text: s.title }));
}

function prettyMaybeJson(text) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}

/* ---------------- analysis ---------------- */
function setResultState(state) {
  $("#results-empty").hidden = state !== "empty";
  $("#results-loading").hidden = state !== "loading";
  $("#results-error").hidden = state !== "error";
  $("#report").hidden = state !== "report";
}

function renderError(err) {
  const box = $("#results-error");
  box.replaceChildren();
  const d = err.body && err.body.detail;
  let title = "Analysis failed";
  let msg = err.message;
  if (err.status === 503) { title = "LLM proxy not configured"; msg = d && d.error ? d.error : msg; }
  else if (err.status === 502 && d) { title = `Validation failed at stage: ${d.stage}`; msg = d.error; }
  else if (err.status === 422) { title = "Invalid input"; msg = JSON.stringify(d); }
  box.append(el("h3", { text: title }), el("p", { class: "mono small", text: msg }));
  if (err.status === 502) {
    box.append(el("p", { class: "muted small",
      text: "No report was fabricated. The model output did not pass schema/citation validation after bounded repair attempts." }));
  }
  setResultState("error");
}

function section(label, ...content) {
  return el("div", { class: "panel" }, el("div", { class: "section-label", text: label }), ...content);
}

function citationChip(id, knownIds) {
  if (!knownIds.has(id)) return el("span", { class: "chip muted-chip", text: id });
  return el("button", { type: "button", class: "chip", text: id, title: "Open playbook", onclick: () => openDoc(id) });
}

function renderReport(payload) {
  const r = payload.report;
  const sev = r.severity_assessment;
  const knownIds = new Set(r.source_citations.map((c) => c.doc_id));
  const root = $("#report");
  root.replaceChildren();

  const head = el("div", { class: "report-head" },
    el("div", { class: `sev-badge sev-${r.severity}`, role: "img", "aria-label": `Severity ${r.severity}` },
      el("span", { class: "lvl", text: r.severity }), el("span", { class: "score", text: `score ${sev.score}` })),
    el("div", {},
      el("div", { class: "muted small mono", text: r.incident_id }),
      el("h2", { text: r.incident_type.replaceAll("_", " ") }),
      el("div", { class: "meta-row" },
        el("span", { class: "tag", text: `confidence: ${r.confidence}` }),
        el("span", { class: "tag", text: `asset tier: ${sev.asset_tier}${sev.asset_known ? "" : " (unknown asset)"}` }),
        r.requires_human_review
          ? el("span", { class: "tag review", text: "requires human review", title: r.review_reasons.join("; ") })
          : el("span", { class: "tag okay", text: "routine review" }),
        el("span", { class: "tag", text: `model: ${payload.model}` }),
        el("span", { class: "tag", text: `${Math.round(payload.timings.total_ms / 100) / 10}s` }))));
  root.append(head);

  const grid = el("div", { class: "report-grid" });
  grid.append(section("Summary — observed facts", el("p", { class: "prose", text: r.summary })));
  grid.append(section("Interpretation — model reading", el("p", { class: "prose", text: r.interpretation })));

  grid.append(section("Severity (deterministic, PB-002)",
    el("p", { class: "mono small", text: sev.explanation }),
    el("p", { class: "muted small", text: "The language model cannot change this value." })));

  const ex = payload.extraction;
  const kv = el("dl", { class: "kv" });
  for (const [k, v] of [["timestamp", ex.timestamp], ["hostname", ex.hostname], ["username", ex.username],
                        ["source ip", ex.source_ip], ["destination ip", ex.destination_ip],
                        ["privileged", String(ex.privileged_account)], ["impact", ex.observed_impact]]) {
    kv.append(el("dt", { text: k }), el("dd", { text: v ?? "— not present" }));
  }
  grid.append(section("Extracted fields (grounded in alert text)", kv));

  grid.append(section("Evidence — verbatim from alert",
    r.evidence.length ? el("ul", { class: "clean evidence" }, r.evidence.map((e) => el("li", { text: e })))
      : el("p", { class: "muted", text: "No verifiable evidence snippets." }),
    r.indicators.length ? el("div", { class: "chips", style: null },
      r.indicators.map((i) => el("span", { class: "chip muted-chip", text: i }))) : null));

  grid.append(section("Recommended next steps — require human approval",
    el("ol", { class: "clean" }, r.recommended_actions.map((a) => el("li", { class: "action" },
      el("span", { text: a.action }),
      el("div", { class: "chips" }, a.citation_ids.map((id) => citationChip(id, knownIds)),
        a.requires_approval ? el("span", { class: "chip muted-chip", text: "approval required" }) : null))))));

  grid.append(section("Source citations",
    r.source_citations.length
      ? el("ul", { class: "clean" }, r.source_citations.map((c) => el("li", {},
          el("button", { type: "button", class: "link", text: `[${c.doc_id}] ${c.title}`, onclick: () => openDoc(c.doc_id) }),
          el("div", { class: "muted small", text: `v${c.version} · ${c.chunk_id || ""}` }))))
      : el("p", { class: "muted", text: "No playbook was cited." })));

  grid.append(section("Limitations & review reasons",
    el("ul", { class: "clean limitations" },
      [...r.limitations, ...r.review_reasons.map((x) => `Review: ${x}`)].map((l) => el("li", { text: l })))));

  const tr = payload.agent_trace;
  grid.append(el("div", { class: "panel wide" },
    el("div", { class: "section-label", text: `Agent tool trace — protocol: ${tr.mode}, stop: ${tr.stop_reason}` }),
    el("ol", { class: "trace" }, tr.steps.map((s) => el("li", { class: `k-${s.kind}` },
      el("div", { class: "t-head", text: `${s.step}. ${s.kind}${s.tool ? ` → ${s.tool}` : ""}` }),
      s.arguments ? el("div", { class: "t-body mono", text: JSON.stringify(s.arguments) }) : null,
      s.result_summary ? el("div", { class: "t-body", text: s.result_summary }) : null,
      s.error ? el("div", { class: "t-body", text: `error: ${s.error}` }) : null)))));

  grid.append(el("div", { class: "panel wide" },
    el("div", { class: "section-label", text: "Retrieved playbook passages" }),
    payload.retrieved.length ? payload.retrieved.map((h) => el("div", { class: "hit" },
      el("div", { class: "hit-head" },
        el("button", { type: "button", class: "link", text: `[${h.doc_id}] ${h.title}`, onclick: () => openDoc(h.doc_id) }),
        el("span", { class: "mono small muted", text: `score ${h.score.toFixed(3)} · ${h.section}` })),
      el("p", { text: h.text.slice(0, 360) + (h.text.length > 360 ? "…" : "") })))
      : el("p", { class: "muted", text: "Retriever abstained: nothing passed the relevance threshold." })));

  root.append(grid);
  setResultState("report");
}

async function analyze(evt) {
  evt.preventDefault();
  const content = $("#alert-text").value;
  if (!content.trim()) return;
  const btn = $("#analyze-btn");
  btn.disabled = true;
  setResultState("loading");
  const sample = SAMPLES.find((s) => s.id === $("#sample-select").value);
  try {
    const payload = await api("/api/analyze", {
      method: "POST", body: JSON.stringify({ content, label: sample ? sample.title : null }),
    });
    renderReport(payload);
  } catch (err) {
    renderError(err);
  } finally {
    btn.disabled = false;
  }
}

/* ---------------- playbook viewer ---------------- */
function renderMarkdownSafe(md, container) {
  container.replaceChildren();
  let list = null;
  for (const raw of md.split("\n")) {
    const line = raw.trim();
    if (!line) { list = null; continue; }
    if (line.startsWith("# ")) continue; // title already shown
    if (line.startsWith("## ")) { list = null; container.append(el("h3", { text: line.slice(3) })); continue; }
    const item = line.match(/^(-|\d+\.)\s+(.*)$/);
    if (item) {
      if (!list) { list = el(item[1] === "-" ? "ul" : "ol"); container.append(list); }
      list.append(el("li", { text: item[2] }));
      continue;
    }
    list = null;
    container.append(el("p", { class: line.startsWith("FICTIONAL POLICY NOTICE") ? "notice" : null, text: line }));
  }
}

async function openDoc(docId) {
  const dlg = $("#doc-dialog");
  try {
    const d = await api(`/api/playbooks/${encodeURIComponent(docId)}`);
    $("#doc-title").textContent = `[${d.doc_id}] ${d.title}`;
    $("#doc-meta").textContent = `${d.category} · v${d.version} · reviewed ${d.last_reviewed} · ${d.source}`;
    renderMarkdownSafe(d.content, $("#doc-body"));
  } catch {
    $("#doc-title").textContent = docId;
    $("#doc-meta").textContent = "";
    $("#doc-body").replaceChildren(el("p", { text: "Document could not be loaded." }));
  }
  if (!dlg.open) dlg.showModal();
}

/* ---------------- knowledge tab ---------------- */
async function loadPlaybooks() {
  const docs = await api("/api/playbooks");
  $("#doc-list").replaceChildren(...docs.map((d) => el("li", {},
    el("button", { type: "button", class: "link", text: `${d.doc_id} · ${d.title}`, onclick: () => openDoc(d.doc_id) }))));
}

async function search(evt) {
  evt.preventDefault();
  const out = $("#search-results");
  out.replaceChildren(el("p", { class: "muted", text: "Searching…" }));
  try {
    const res = await api("/api/search", { method: "POST", body: JSON.stringify({ query: $("#search-input").value, top_k: 3 }) });
    out.replaceChildren();
    if (res.abstained) {
      out.append(el("div", { class: "hit" }, el("strong", { text: "No playbook passed the relevance threshold." }),
        el("p", { text: `Top score ${res.top_score.toFixed(3)} < threshold ${res.min_score}. The system abstains rather than citing a weak match.` })));
      return;
    }
    for (const h of res.hits) {
      out.append(el("div", { class: "hit" },
        el("div", { class: "hit-head" },
          el("button", { type: "button", class: "link", text: `[${h.doc_id}] ${h.title}`, onclick: () => openDoc(h.doc_id) }),
          el("span", { class: "mono small muted", text: `score ${h.score.toFixed(3)}` })),
        el("p", { text: h.text.slice(0, 300) + "…" })));
    }
  } catch (err) {
    out.replaceChildren(el("p", { class: "muted", text: `Search failed (${err.message}). Query must be 3–500 characters.` }));
  }
}

async function loadAssets() {
  const assets = await api("/api/assets");
  const sel = $("#sev-host");
  sel.append(el("option", { value: "", text: "(unknown / not in catalogue)" }));
  for (const a of assets) sel.append(el("option", { value: a.hostname, text: `${a.hostname} — ${a.role} (${a.tier})` }));
}

async function calcSeverity(evt) {
  evt.preventDefault();
  const body = {
    hostname: $("#sev-host").value || null,
    alert_confidence: $("#sev-conf").value,
    observed_impact: $("#sev-impact").value,
    privileged_account: $("#sev-priv").checked,
  };
  const out = $("#severity-result");
  try {
    const r = await api("/api/severity", { method: "POST", body: JSON.stringify(body) });
    out.replaceChildren(el("div", { class: "sev-result" },
      el("div", { class: `sev-badge sev-${r.severity}` }, el("span", { class: "lvl", text: r.severity }),
        el("span", { class: "score", text: `score ${r.score}` })),
      el("p", { class: "mono small", text: r.explanation })));
  } catch (err) {
    out.replaceChildren(el("p", { class: "muted", text: `Calculation failed: ${err.message}` }));
  }
}

/* ---------------- history ---------------- */
async function loadAnalyses() {
  const tbody = $("#analyses-table tbody");
  const rows = await api("/api/analyses");
  tbody.replaceChildren();
  if (!rows.length) {
    tbody.append(el("tr", {}, el("td", { colspan: "5", class: "muted", text: "No analyses saved yet." })));
    return;
  }
  for (const r of rows) {
    tbody.append(el("tr", { class: "clickable", tabindex: "0", onclick: () => openAnalysis(r.incident_id),
      onkeydown: (e) => { if (e.key === "Enter") openAnalysis(r.incident_id); } },
      el("td", { class: "mono", text: r.incident_id }), el("td", { text: r.created_at }),
      el("td", { text: r.incident_type }), el("td", {}, el("span", { class: `sev-${r.severity}`, text: r.severity })),
      el("td", { text: r.requires_review ? "yes" : "no" })));
  }
}

async function openAnalysis(id) {
  const payload = await api(`/api/analyses/${encodeURIComponent(id)}`);
  showTab("investigate");
  renderReport(payload);
}

async function loadHistory(evt) {
  if (evt) evt.preventDefault();
  const type = $("#history-type").value;
  const rows = await api(`/api/history${type ? `?incident_type=${encodeURIComponent(type)}` : ""}`);
  $("#history-table tbody").replaceChildren(...(rows.length ? rows.map((r) => el("tr", {},
    el("td", { class: "mono", text: r.case_id }), el("td", { text: r.opened }), el("td", { text: r.incident_type }),
    el("td", { class: "mono", text: r.hostname }), el("td", {}, el("span", { class: `sev-${r.severity}`, text: r.severity })),
    el("td", { text: r.summary }), el("td", { class: "mono", text: r.closure_code })))
    : [el("tr", {}, el("td", { colspan: "7", class: "muted", text: "No matching incidents." }))]));
}

/* ---------------- evaluation ---------------- */
const fmt = (v) => (typeof v === "number" ? v.toFixed(3) : "—");

async function loadEvaluation() {
  const panel = $("#eval-panel");
  const data = await api("/api/eval/summary");
  panel.replaceChildren();
  if (!data.retrieval) {
    panel.append(el("p", { class: "muted", text: "No evaluation results found. Run: python -m eval.run_retrieval_eval" }));
    return;
  }
  const s = data.retrieval;
  const m = s.meta;
  panel.append(el("div", { class: "panel-head" }, el("h2", { text: "Retrieval evaluation (held-out test split)" }),
    el("span", { class: "muted small mono", text: `dataset ${m.dataset} · sha ${m.dataset_sha256_16} · ${m.generated_at}` })));
  const metrics = ["recall@3", "mrr@5", "precision@3", "hit@1", "abstention_accuracy"];
  const table = el("table", { class: "table" },
    el("thead", {}, el("tr", {}, el("th", { text: "Configuration" }), metrics.map((k) => el("th", { text: k })))),
    el("tbody", {},
      el("tr", {}, el("td", { text: `Baseline A: ${s.baseline.name}` }), metrics.map((k) => el("td", { class: "num", text: fmt(s.baseline.test[k]) }))),
      el("tr", { class: "highlight" }, el("td", { text: `Selected B: ${s.selected.name}` }), metrics.map((k) => el("td", { class: "num", text: fmt(s.selected.test[k]) })))));
  panel.append(el("div", { class: "table-wrap" }, table));
  const p = s["test_paired_rr@5_vs_baseline"];
  panel.append(el("p", { class: "metric-note", text:
    `Test: ${m.dataset_counts.test} queries (${m.dataset_counts.test_answerable} answerable). Selection rule (dev only): ${m.selection_rule}. ` +
    `Per-query RR@5 vs baseline on test: ${p.wins} wins, ${p.losses} losses, ${p.ties} ties. ` +
    "Ranking metrics use answerable queries; abstention accuracy uses all queries." }));

  if (data.runs) {
    panel.append(el("h3", { class: "sub", text: "All configurations (dev used for selection; test shown for transparency)" }));
    panel.append(el("div", { class: "table-wrap" }, el("table", { class: "table" },
      el("thead", {}, el("tr", {}, ["Config", "dev R@3", "dev MRR@5", "dev abst.", "test R@3", "test MRR@5", "test abst.", "threshold"].map((h) => el("th", { text: h })))),
      el("tbody", {}, data.runs.map((r) => el("tr", { class: r.name === s.selected.name ? "highlight" : null },
        el("td", { class: "mono", text: r.name }),
        el("td", { class: "num", text: fmt(r.dev["recall@3"]) }), el("td", { class: "num", text: fmt(r.dev["mrr@5"]) }),
        el("td", { class: "num", text: fmt(r.dev.abstention_accuracy) }),
        el("td", { class: "num", text: fmt(r.test["recall@3"]) }), el("td", { class: "num", text: fmt(r.test["mrr@5"]) }),
        el("td", { class: "num", text: fmt(r.test.abstention_accuracy) }), el("td", { class: "num", text: String(r.threshold) })))))));
  }
  if (data.e2e) {
    panel.append(el("h3", { class: "sub", text: "End-to-end (live LLM) evaluation" }));
    panel.append(el("pre", { class: "mono small", text: JSON.stringify(data.e2e.aggregate || data.e2e, null, 2) }));
  } else {
    panel.append(el("p", { class: "metric-note", text: "End-to-end LLM evaluation: pending (requires class proxy credentials; run python -m eval.run_e2e_eval)." }));
  }
}

/* ---------------- init ---------------- */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
  $("#alert-form").addEventListener("submit", analyze);
  $("#alert-text").addEventListener("input", (e) => { $("#char-count").textContent = `${e.target.value.length} / 20000`; });
  $("#sample-select").addEventListener("change", (e) => {
    const s = SAMPLES.find((x) => x.id === e.target.value);
    if (!s) return;
    $("#alert-text").value = prettyMaybeJson(s.content);
    $("#char-count").textContent = `${$("#alert-text").value.length} / 20000`;
  });
  $("#search-form").addEventListener("submit", search);
  $("#severity-form").addEventListener("submit", calcSeverity);
  $("#history-form").addEventListener("submit", loadHistory);
  $("#refresh-analyses").addEventListener("click", loadAnalyses);
  $("#doc-close").addEventListener("click", () => $("#doc-dialog").close());
  for (const t of INCIDENT_TYPES) $("#history-type").append(el("option", { value: t, text: t }));
  setResultState("empty");
  loadHealth();
  loadSamples();
  loadPlaybooks();
  loadAssets();
});
