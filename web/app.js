// SentinelAI dashboard. All dynamic text is inserted with textContent (no innerHTML of data).
"use strict";

const $ = (sel) => document.querySelector(sel);
const SVG_NS = "http://www.w3.org/2000/svg";

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

// References a <symbol> from the sprite in index.html.
function icon(name, extraClass = "") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", `ico ${extraClass}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
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

let toastTimer = null;
function toast(message, iconName = "check") {
  const t = $("#toast");
  t.replaceChildren(icon(iconName), el("span", { text: message }));
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

const INCIDENT_TYPES = ["brute_force", "suspicious_login", "privileged_account_compromise", "malware",
  "suspicious_powershell", "command_injection", "unusual_outbound", "data_exfiltration", "suspicious_dns",
  "phishing", "false_positive", "undetermined"];
const label = (s) => String(s).replaceAll("_", " ");

/* ---------------- tabs ---------------- */
function showTab(name, focus = false) {
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.tab === name;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    if (on && focus) t.focus();
  });
  document.querySelectorAll(".view").forEach((v) => { v.hidden = v.id !== `view-${name}`; });
  if (name === "history") { loadAnalyses(); loadHistory(); }
  if (name === "evaluation") loadEvaluation();
}

function onTabKey(evt) {
  const tabs = [...document.querySelectorAll(".tab")];
  const i = tabs.indexOf(evt.currentTarget);
  let next = null;
  if (evt.key === "ArrowRight") next = tabs[(i + 1) % tabs.length];
  else if (evt.key === "ArrowLeft") next = tabs[(i - 1 + tabs.length) % tabs.length];
  else if (evt.key === "Home") next = tabs[0];
  else if (evt.key === "End") next = tabs[tabs.length - 1];
  if (!next) return;
  evt.preventDefault();
  showTab(next.dataset.tab, true);
}

/* ---------------- status ---------------- */
async function loadHealth() {
  const llm = $("#status-llm");
  const text = llm.querySelector(".pill-text");
  try {
    const h = await api("/api/health");
    text.textContent = h.llm_configured ? `LLM: ${h.model}` : "LLM: not configured";
    llm.className = `pill ${h.llm_configured ? "ok" : "warn"}`;
    llm.title = h.llm_configured ? "Class proxy configured" : "Set OPENAI_API_KEY and OPENAI_BASE_URL to enable analysis";
    const r = h.retrieval;
    const name = r.method === "bm25" ? `bm25 · ${r.chunking}` : `${r.method} · ${r.dense_backend} · α=${r.hybrid_alpha}`;
    $("#status-retrieval").textContent = `RAG: ${name}${r.fallback ? " (fallback)" : ""} · ${h.documents} docs`;
  } catch {
    text.textContent = "API unreachable";
    llm.className = "pill warn";
  }
}

/* ---------------- samples ---------------- */
let SAMPLES = [];
const QUICK_SAMPLES = ["vpn-success-after-failures", "insufficient", "prompt-injection"];

function loadSample(id) {
  const s = SAMPLES.find((x) => x.id === id);
  if (!s) return;
  $("#sample-select").value = s.id;
  $("#alert-text").value = prettyMaybeJson(s.content);
  updateCount();
}

async function loadSamples() {
  try {
    SAMPLES = await api("/api/samples");
  } catch {
    return;
  }
  const sel = $("#sample-select");
  for (const s of SAMPLES) sel.append(el("option", { value: s.id, text: s.title }));
  const quick = QUICK_SAMPLES.map((id) => SAMPLES.find((s) => s.id === id)).filter(Boolean);
  if (quick.length) {
    $("#quick-row").replaceChildren(...quick.map((s) => el("button", {
      type: "button", class: "btn-ghost btn-sm",
      onclick: () => { loadSample(s.id); $("#alert-text").focus(); },
    }, icon("file"), s.title)));
    $("#quick-samples").hidden = false;
  }
}

function prettyMaybeJson(text) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}

function updateCount() {
  $("#char-count").textContent = `${$("#alert-text").value.length.toLocaleString()} / 20,000`;
}

/* ---------------- analysis ---------------- */
let elapsedTimer = null;

function setResultState(state) {
  $("#results-empty").hidden = state !== "empty";
  $("#results-loading").hidden = state !== "loading";
  $("#results-error").hidden = state !== "error";
  $("#report").hidden = state !== "report";
  $("#results").setAttribute("aria-busy", String(state === "loading"));
  if (state === "loading") $("#results-status").textContent = "Analysis started.";
  clearInterval(elapsedTimer);
  if (state === "loading") {
    const start = Date.now();
    $("#elapsed").textContent = "0s";
    elapsedTimer = setInterval(() => { $("#elapsed").textContent = `${Math.round((Date.now() - start) / 1000)}s`; }, 1000);
  }
}

function renderError(err) {
  const box = $("#results-error");
  box.replaceChildren();
  const d = err.body && err.body.detail;
  let title = "Analysis failed";
  let msg = err.message;
  let hint = null;
  if (err.status === undefined) {
    title = "Cannot reach the SentinelAI API";
    msg = "The request did not reach the server.";
    hint = "Check that uvicorn is still running on this port, then retry.";
  } else if (err.status === 503) {
    title = "LLM proxy unavailable";
    msg = d && d.error ? d.error : msg;
    hint = "Check the class proxy with: python -m scripts.check_proxy. Search, severity and evaluation still work without it.";
  } else if (err.status === 502 && d) {
    title = `Validation failed at stage: ${d.stage}`;
    msg = d.error;
    hint = "No report was fabricated. The model output did not pass schema/citation validation after bounded repair attempts.";
  } else if (err.status === 422) {
    title = "Invalid input";
    msg = JSON.stringify(d);
  } else if (err.status === 413) {
    title = "Alert is too large";
    msg = "The request body exceeded the server limit.";
    hint = "Trim the alert to the relevant lines and try again.";
  } else if (err.status === 429) {
    title = "Another analysis is running";
    msg = "The server limits concurrent analyses.";
    hint = "Wait for the current run to finish, then retry.";
  }
  box.append(icon("alert"), el("h3", { text: title }), el("p", { class: "mono small", text: msg }));
  if (hint) box.append(el("p", { class: "muted small", text: hint }));
  box.append(el("button", { type: "button", class: "btn-ghost btn-sm", onclick: () => $("#alert-form").requestSubmit() },
    icon("refresh"), "Retry"));
  setResultState("error");
}

function section(labelText, iconName, ...content) {
  return el("div", { class: "panel" },
    el("h3", { class: "section-label" }, icon(iconName), labelText), ...content);
}

function citationChip(id, knownIds) {
  if (!knownIds.has(id)) return el("span", { class: "chip muted-chip", text: id });
  return el("button", { type: "button", class: "chip", title: `Open playbook ${id}`, onclick: () => openDoc(id) },
    icon("link"), id);
}

function sevPill(level) {
  return el("span", { class: `sev-pill sev-${level}`, text: level });
}

let CURRENT = null;

async function copyReport() {
  if (!CURRENT) return;
  try {
    await navigator.clipboard.writeText(JSON.stringify(CURRENT.report, null, 2));
    toast("Report JSON copied to clipboard");
  } catch {
    toast("Clipboard is not available in this browser", "alert");
  }
}

function scoreBar(score) {
  const fill = el("i");
  fill.style.width = `${Math.max(0, Math.min(1, score)) * 100}%`;
  return el("span", { class: "score-bar mono small muted" }, el("span", { class: "bar", "aria-hidden": "true" }, fill),
    `score ${score.toFixed(3)}`);
}

function renderReport(payload) {
  CURRENT = payload;
  const r = payload.report;
  const sev = r.severity_assessment;
  const knownIds = new Set(r.source_citations.map((c) => c.doc_id));
  const root = $("#report");
  root.replaceChildren();

  const head = el("div", { class: "report-head" },
    el("div", { class: `sev-badge sev-${r.severity}`, role: "img", "aria-label": `Severity ${r.severity}, score ${sev.score}` },
      el("span", { class: "lvl", text: r.severity }), el("span", { class: "score", text: `score ${sev.score}` })),
    el("div", {},
      el("div", { class: "muted small mono", text: r.incident_id }),
      el("h2", { text: label(r.incident_type) }),
      el("div", { class: "meta-row" },
        el("span", { class: "tag" }, icon("gauge"), `confidence: ${r.confidence}`),
        el("span", { class: "tag" }, icon("server"), `asset tier: ${sev.asset_tier}${sev.asset_known ? "" : " (unknown asset)"}`),
        r.requires_human_review
          ? el("span", { class: "tag review", title: r.review_reasons.join("; ") }, icon("user-check"), "requires human review")
          : el("span", { class: "tag okay" }, icon("check"), "routine review"),
        el("span", { class: "tag" }, icon("cpu"), payload.model),
        el("span", { class: "tag" }, icon("clock"), `${Math.round(payload.timings.total_ms / 100) / 10}s`))),
    el("div", { class: "report-actions" },
      el("button", { type: "button", class: "btn-ghost btn-sm", onclick: copyReport }, icon("copy"), "Copy JSON")));
  root.append(head);

  const grid = el("div", { class: "report-grid" });
  grid.append(section("Summary — observed facts", "quote", el("p", { class: "prose", text: r.summary })));
  grid.append(section("Interpretation — model reading", "message", el("p", { class: "prose", text: r.interpretation })));

  grid.append(section("Severity (deterministic, PB-002)", "gauge",
    el("p", { class: "mono small prose", text: sev.explanation }),
    el("p", { class: "muted small prose", text: "The language model cannot change this value." })));

  const ex = payload.extraction;
  const kv = el("dl", { class: "kv" });
  for (const [k, v] of [["timestamp", ex.timestamp], ["hostname", ex.hostname], ["username", ex.username],
                        ["source ip", ex.source_ip], ["destination ip", ex.destination_ip],
                        ["privileged", String(ex.privileged_account)], ["impact", ex.observed_impact]]) {
    const missing = v === null || v === undefined || v === "";
    kv.append(el("dt", { text: k }), el("dd", { class: missing ? "absent" : null, text: missing ? "not present" : v }));
  }
  grid.append(section("Extracted fields (grounded in alert text)", "tag", kv));

  grid.append(section("Evidence — verbatim from alert", "file",
    r.evidence.length ? el("ul", { class: "clean evidence" }, r.evidence.map((e) => el("li", { text: e })))
      : el("p", { class: "muted", text: "No verifiable evidence snippets." }),
    r.indicators.length ? el("div", { class: "chips" },
      r.indicators.map((i) => el("span", { class: "chip muted-chip", text: i }))) : null));

  grid.append(section("Recommended next steps — require human approval", "list",
    r.recommended_actions.length
      ? el("ol", { class: "clean actions" }, r.recommended_actions.map((a) => el("li", { class: "action" },
          el("span", { text: a.action }),
          el("div", { class: "chips" }, a.citation_ids.map((id) => citationChip(id, knownIds)),
            a.requires_approval ? el("span", { class: "chip muted-chip" }, icon("lock"), "approval required") : null))))
      : el("p", { class: "muted", text: "No actions recommended." })));

  grid.append(section("Source citations", "link",
    r.source_citations.length
      ? el("ul", { class: "clean" }, r.source_citations.map((c) => el("li", { class: "cite-item" }, icon("book"),
          el("div", {},
            el("button", { type: "button", class: "link", text: `[${c.doc_id}] ${c.title}`, onclick: () => openDoc(c.doc_id) }),
            el("div", { class: "muted small", text: `v${c.version}${c.chunk_id ? ` · ${c.chunk_id}` : ""}` })))))
      : el("p", { class: "muted", text: "No playbook was cited." })));

  const limits = [...r.limitations, ...r.review_reasons.map((x) => `Review: ${x}`)];
  grid.append(section("Limitations & review reasons", "alert",
    limits.length ? el("ul", { class: "clean limitations" }, limits.map((l) => el("li", { text: l })))
      : el("p", { class: "muted", text: "None reported." })));

  const tr = payload.agent_trace;
  grid.append(el("div", { class: "panel wide" },
    el("h3", { class: "section-label" }, icon("branch"), `Agent tool trace — protocol: ${tr.mode}, stop: ${tr.stop_reason}`),
    el("ol", { class: "trace" }, tr.steps.map((s) => el("li", { class: `k-${s.kind}` },
      el("div", { class: "t-head" }, `${s.step}. ${s.kind}`, s.tool ? el("span", { class: "t-tool", text: ` → ${s.tool}` }) : null),
      s.arguments ? el("code", { class: "t-args", text: JSON.stringify(s.arguments) }) : null,
      s.result_summary ? el("div", { class: "t-body", text: s.result_summary }) : null,
      s.error ? el("div", { class: "t-body", text: `error: ${s.error}` }) : null)))));

  grid.append(el("div", { class: "panel wide" },
    el("h3", { class: "section-label" }, icon("layers"), "Retrieved playbook passages"),
    payload.retrieved.length ? payload.retrieved.map((h) => el("div", { class: "hit" },
      el("div", { class: "hit-head" },
        el("button", { type: "button", class: "link", text: `[${h.doc_id}] ${h.title}`, onclick: () => openDoc(h.doc_id) }),
        el("span", { class: "mono small muted" }, scoreBar(h.score), ` · ${h.section}`)),
      el("p", { text: h.text.slice(0, 360) + (h.text.length > 360 ? "…" : "") })))
      : el("p", { class: "muted", text: "Retriever abstained: nothing passed the relevance threshold." })));

  root.append(grid);
  setResultState("report");
  $("#results-status").textContent = `Report ready: ${r.severity} severity, ${label(r.incident_type)}` +
    (r.requires_human_review ? ", requires human review." : ".");
}

async function analyze(evt) {
  evt.preventDefault();
  const content = $("#alert-text").value;
  if (!content.trim()) { $("#alert-text").focus(); return; }
  const btn = $("#analyze-btn");
  btn.disabled = true;
  btn.replaceChildren(el("span", { class: "btn-spin", "aria-hidden": "true" }), el("span", { class: "btn-label", text: "Analyzing…" }));
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
    btn.replaceChildren(icon("play"), el("span", { class: "btn-label", text: "Analyze alert" }));
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
  dlg.scrollTop = 0;
}

/* ---------------- knowledge tab ---------------- */
async function loadPlaybooks() {
  try {
    const docs = await api("/api/playbooks");
    $("#doc-count").textContent = String(docs.length);
    $("#doc-list").replaceChildren(...docs.map((d) => el("li", {},
      el("button", { type: "button", class: "link", onclick: () => openDoc(d.doc_id) },
        el("span", { class: "doc-id", text: d.doc_id }), el("span", { class: "doc-name", text: d.title })))));
  } catch {
    $("#doc-list").replaceChildren(el("li", { class: "muted", text: "Playbooks could not be loaded." }));
  }
}

async function search(evt) {
  evt.preventDefault();
  const out = $("#search-results");
  out.replaceChildren(el("p", { class: "muted", text: "Searching…" }));
  try {
    const res = await api("/api/search", { method: "POST", body: JSON.stringify({ query: $("#search-input").value, top_k: 3 }) });
    out.replaceChildren();
    if (res.abstained) {
      out.append(el("div", { class: "hit abstain" }, el("strong", {}, icon("info"), "No playbook passed the relevance threshold."),
        el("p", { text: `Top score ${res.top_score.toFixed(3)} < threshold ${res.min_score}. The system abstains rather than citing a weak match.` })));
      return;
    }
    for (const h of res.hits) {
      out.append(el("div", { class: "hit" },
        el("div", { class: "hit-head" },
          el("button", { type: "button", class: "link", text: `[${h.doc_id}] ${h.title}`, onclick: () => openDoc(h.doc_id) }),
          scoreBar(h.score)),
        el("p", { text: h.text.slice(0, 300) + (h.text.length > 300 ? "…" : "") })));
    }
  } catch (err) {
    out.replaceChildren(el("p", { class: "muted", text: `Search failed (${err.message}). Query must be 3–500 characters.` }));
  }
}

async function loadAssets() {
  const sel = $("#sev-host");
  sel.append(el("option", { value: "", text: "(unknown / not in catalogue)" }));
  try {
    const assets = await api("/api/assets");
    for (const a of assets) sel.append(el("option", { value: a.hostname, text: `${a.hostname} — ${a.role} (${a.tier})` }));
  } catch { /* calculator still works for unknown assets */ }
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
      el("div", { class: `sev-badge sev-${r.severity}`, role: "img", "aria-label": `Severity ${r.severity}, score ${r.score}` },
        el("span", { class: "lvl", text: r.severity }), el("span", { class: "score", text: `score ${r.score}` })),
      el("p", { class: "mono small", text: r.explanation })));
  } catch (err) {
    out.replaceChildren(el("p", { class: "muted", text: `Calculation failed: ${err.message}` }));
  }
}

/* ---------------- history ---------------- */
function emptyRow(cols, text) {
  return el("tr", {}, el("td", { colspan: String(cols), class: "empty-row", text }));
}

async function loadAnalyses() {
  const tbody = $("#analyses-table tbody");
  let rows;
  try {
    rows = await api("/api/analyses");
  } catch {
    tbody.replaceChildren(emptyRow(5, "Saved analyses could not be loaded."));
    return;
  }
  tbody.replaceChildren();
  if (!rows.length) {
    tbody.append(emptyRow(5, "No analyses saved yet. Run one from the Investigate tab."));
    return;
  }
  for (const r of rows) {
    tbody.append(el("tr", { class: "clickable", tabindex: "0", title: "Open this analysis", onclick: () => openAnalysis(r.incident_id),
      onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openAnalysis(r.incident_id); } } },
      el("td", { class: "mono", text: r.incident_id }), el("td", { class: "mono", text: r.created_at }),
      el("td", { text: label(r.incident_type) }), el("td", {}, sevPill(r.severity)),
      el("td", {}, r.requires_review
        ? el("span", { class: "tag review" }, icon("user-check"), "required")
        : el("span", { class: "tag okay" }, icon("check"), "routine"))));
  }
}

async function openAnalysis(id) {
  try {
    const payload = await api(`/api/analyses/${encodeURIComponent(id)}`);
    showTab("investigate");
    renderReport(payload);
  } catch {
    toast("This analysis could not be loaded", "alert");
  }
}

async function loadHistory(evt) {
  if (evt) evt.preventDefault();
  const type = $("#history-type").value;
  const tbody = $("#history-table tbody");
  let rows;
  try {
    rows = await api(`/api/history${type ? `?incident_type=${encodeURIComponent(type)}` : ""}`);
  } catch {
    tbody.replaceChildren(emptyRow(7, "Incident history could not be loaded."));
    return;
  }
  tbody.replaceChildren(...(rows.length ? rows.map((r) => el("tr", {},
    el("td", { class: "mono", text: r.case_id }), el("td", { class: "mono", text: r.opened }), el("td", { text: label(r.incident_type) }),
    el("td", { class: "mono", text: r.hostname }), el("td", {}, sevPill(r.severity)),
    el("td", { text: r.summary }), el("td", { class: "mono", text: r.closure_code })))
    : [emptyRow(7, "No matching incidents.")]));
}

/* ---------------- evaluation ---------------- */
const fmt = (v) => (typeof v === "number" ? v.toFixed(3) : "—");

const E2E_METRICS = [
  ["valid_structured_output_rate", "Valid structured output"],
  ["incident_type_accuracy", "Incident type accuracy"],
  ["severity_accuracy", "Severity accuracy", "severity_cases"],
  ["citation_validity_rate", "Citation validity"],
  ["relevant_citation_rate", "Relevant citation"],
  ["undetermined_flagged_rate", "Undetermined flagged for review"],
  ["native_tool_mode_rate", "Native tool-calling mode"],
];

function renderE2E(e2e) {
  const agg = e2e.aggregate || {};
  const m = e2e.meta || {};
  const panel = el("div", { class: "panel" },
    el("div", { class: "panel-head" }, el("h2", {}, icon("cpu"), "End-to-end evaluation (live LLM)"),
      el("div", { class: "meta-line" },
        m.model ? el("span", { class: "tag" }, icon("cpu"), m.model) : null,
        m.temperature !== undefined ? el("span", { class: "tag", text: `temperature ${m.temperature}` }) : null,
        m.split ? el("span", { class: "tag", text: `split: ${m.split}` }) : null,
        m.round ? el("span", { class: "tag", text: m.round }) : null)));
  const grid = el("dl", { class: "metric-grid" });
  for (const [key, name, countKey] of E2E_METRICS) {
    if (agg[key] === undefined) continue;
    grid.append(el("div", { class: "metric" }, el("dt", { text: name }),
      el("dd", {}, fmt(agg[key]), countKey && agg[countKey] !== undefined ? el("small", { text: `n=${agg[countKey]}` }) : null)));
  }
  panel.append(grid);
  panel.append(el("p", { class: "metric-note", text:
    `${agg.cases_run ?? "—"} cases run${m.generated_at ? ` · generated ${m.generated_at}` : ""}. ` +
    "Round-by-round results on blind holdout sets are in docs/EXPERIMENT_LOG.md." }));
  return panel;
}

async function loadEvaluation() {
  const root = $("#eval-root");
  let data;
  try {
    data = await api("/api/eval/summary");
  } catch {
    root.replaceChildren(el("div", { class: "panel" }, el("p", { class: "muted", text: "Evaluation results could not be loaded." })));
    return;
  }
  root.replaceChildren();
  if (!data.retrieval) {
    root.append(el("div", { class: "panel" }, el("p", { class: "muted", text: "No evaluation results found. Run: python -m eval.run_retrieval_eval" })));
    return;
  }
  const s = data.retrieval;
  const m = s.meta;
  const panel = el("div", { class: "panel" });
  panel.append(el("div", { class: "panel-head" }, el("h2", {}, icon("search"), "Retrieval evaluation (held-out test split)"),
    el("span", { class: "muted small mono", text: `dataset ${m.dataset} · sha ${m.dataset_sha256_16} · ${m.generated_at}` })));
  const metrics = ["recall@3", "mrr@5", "precision@3", "hit@1", "abstention_accuracy"];
  const table = el("table", { class: "table" },
    el("thead", {}, el("tr", {}, el("th", { text: "Configuration" }), metrics.map((k) => el("th", { class: "num", text: k })))),
    el("tbody", {},
      el("tr", {}, el("td", { text: `Baseline A: ${s.baseline.name}` }), metrics.map((k) => el("td", { class: "num", text: fmt(s.baseline.test[k]) }))),
      el("tr", { class: "highlight" }, el("td", { text: `Selected B: ${s.selected.name}` }),
        metrics.map((k) => el("td", { class: `num${s.selected.test[k] > s.baseline.test[k] ? " best" : ""}`, text: fmt(s.selected.test[k]) })))));
  panel.append(el("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Retrieval baseline vs selected" }, table));
  const p = s["test_paired_rr@5_vs_baseline"];
  panel.append(el("p", { class: "metric-note", text:
    `Test: ${m.dataset_counts.test} queries (${m.dataset_counts.test_answerable} answerable). Selection rule (dev only): ${m.selection_rule}. ` +
    `Per-query RR@5 vs baseline on test: ${p.wins} wins, ${p.losses} losses, ${p.ties} ties. ` +
    "Ranking metrics use answerable queries; abstention accuracy uses all queries." }));

  if (data.runs) {
    panel.append(el("h3", { class: "sub", text: "All configurations (dev used for selection; test shown for transparency)" }));
    panel.append(el("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "All retrieval configurations" }, el("table", { class: "table" },
      el("thead", {}, el("tr", {}, ["Config", "dev R@3", "dev MRR@5", "dev abst.", "test R@3", "test MRR@5", "test abst.", "threshold"]
        .map((h, i) => el("th", { class: i ? "num" : null, text: h })))),
      el("tbody", {}, data.runs.map((r) => el("tr", { class: r.name === s.selected.name ? "highlight" : null },
        el("td", { class: "mono", text: r.name }),
        el("td", { class: "num", text: fmt(r.dev["recall@3"]) }), el("td", { class: "num", text: fmt(r.dev["mrr@5"]) }),
        el("td", { class: "num", text: fmt(r.dev.abstention_accuracy) }),
        el("td", { class: "num", text: fmt(r.test["recall@3"]) }), el("td", { class: "num", text: fmt(r.test["mrr@5"]) }),
        el("td", { class: "num", text: fmt(r.test.abstention_accuracy) }), el("td", { class: "num", text: String(r.threshold) })))))));
  }
  root.append(data.e2e ? renderE2E(data.e2e) : el("div", { class: "panel" }, el("p", { class: "metric-note",
    text: "End-to-end LLM evaluation: pending (requires class proxy credentials; run python -m eval.run_e2e_eval)." })));
  root.append(panel);
}

/* ---------------- init ---------------- */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => showTab(t.dataset.tab));
    t.addEventListener("keydown", onTabKey);
  });
  $("#alert-form").addEventListener("submit", analyze);
  $("#alert-text").addEventListener("input", updateCount);
  $("#alert-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $("#alert-form").requestSubmit(); }
  });
  $("#sample-select").addEventListener("change", (e) => loadSample(e.target.value));
  $("#search-form").addEventListener("submit", search);
  $("#severity-form").addEventListener("submit", calcSeverity);
  $("#history-form").addEventListener("submit", loadHistory);
  $("#refresh-analyses").addEventListener("click", loadAnalyses);
  const dlg = $("#doc-dialog");
  $("#doc-close").addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  for (const t of INCIDENT_TYPES) $("#history-type").append(el("option", { value: t, text: label(t) }));
  updateCount();
  setResultState("empty");
  loadHealth();
  loadSamples();
  loadPlaybooks();
  loadAssets();
});
