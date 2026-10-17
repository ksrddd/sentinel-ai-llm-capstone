"""Integration tests: full pipeline and REST API with a mocked LLM client."""

import dataclasses
import json

import pytest
from conftest import BRUTE_FORCE_ALERT, GOOD_DRAFT, GOOD_EXTRACTION, ScriptedLLM, text, tool_call
from fastapi.testclient import TestClient

from app.main import create_app


def happy_script(draft=GOOD_DRAFT, extraction=GOOD_EXTRACTION):
    return [
        text(extraction),
        tool_call("search_playbooks", {"query": "many failed logons from one external address"}),
        tool_call("calculate_severity", {"hostname": "WS-FIN-114", "alert_confidence": "high",
                                         "observed_impact": "none", "privileged_account": False}, "c2"),
        text("Brute-force attempt, no success observed."),
        text(draft),
    ]


def make_client(settings, llm=None):
    return TestClient(create_app(settings, llm=llm))


def test_full_analysis_with_mocked_llm(offline_settings):
    llm = ScriptedLLM(happy_script())
    client = make_client(offline_settings, llm)
    r = client.post("/api/analyze", json={"content": BRUTE_FORCE_ALERT, "label": "test"})
    assert r.status_code == 200, r.text
    body = r.json()
    rep = body["report"]
    assert rep["severity"] == "Low" and rep["severity_assessment"]["score"] == 5
    assert [c["doc_id"] for c in rep["source_citations"]] == ["PB-004"]
    assert rep["affected_assets"][0] == "WS-FIN-114"
    assert body["agent_trace"]["stop_reason"] == "completed"
    assert {s["tool"] for s in body["agent_trace"]["steps"] if s["kind"] == "tool_call"} == {
        "search_playbooks", "calculate_severity"}
    assert all(c["doc_id"] in {h["doc_id"] for h in body["retrieved"]} for c in rep["source_citations"])
    # persisted and retrievable
    saved = client.get(f"/api/analyses/{rep['incident_id']}")
    assert saved.status_code == 200 and saved.json()["report"]["incident_id"] == rep["incident_id"]
    assert client.get("/api/analyses").json()[0]["incident_id"] == rep["incident_id"]


def test_fabricated_citation_is_repaired(offline_settings):
    bad = {**GOOD_DRAFT, "cited_doc_ids": ["PB-999"],
           "recommended_actions": [{"action": "Do X", "citation_ids": ["PB-999"]}]}
    script = happy_script(draft=bad) + [text(GOOD_DRAFT)]
    llm = ScriptedLLM(script)
    r = make_client(offline_settings, llm).post("/api/analyze", json={"content": BRUTE_FORCE_ALERT})
    assert r.status_code == 200
    assert r.json()["attempts"]["report"] == 2
    assert "PB-999" in llm.calls[-1]["messages"][-1]["content"]


def test_persistent_fabricated_citation_returns_validation_error(offline_settings):
    bad = {**GOOD_DRAFT, "cited_doc_ids": ["PB-999"]}
    llm = ScriptedLLM(happy_script(draft=bad) + [text(bad), text(bad)])
    r = make_client(offline_settings, llm).post("/api/analyze", json={"content": BRUTE_FORCE_ALERT})
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert detail["stage"] == "report" and "PB-999" in detail["error"]


def test_agent_skipping_tools_triggers_enforced_calls_and_grounding(offline_settings):
    """Model invents a hostname and finishes without tools: orchestrator still runs required tools."""
    invented = {**GOOD_EXTRACTION, "hostname": "HQ-DC01"}  # not in the alert text
    llm = ScriptedLLM([text(invented), text("Looks fine."), text(GOOD_DRAFT)])
    r = make_client(offline_settings, llm).post("/api/analyze", json={"content": BRUTE_FORCE_ALERT})
    assert r.status_code == 200, r.text
    body = r.json()
    kinds = [s["kind"] for s in body["agent_trace"]["steps"]]
    assert kinds.count("enforced_tool_call") == 2
    rep = body["report"]
    assert "HQ-DC01" not in rep["affected_assets"]
    assert rep["severity_assessment"]["asset_known"] is False
    assert rep["requires_human_review"] and "ungrounded model output removed" in rep["review_reasons"]


def test_undetermined_alert_searches_insufficient_evidence_guidance(offline_settings):
    """Vague alert: besides the agent's own search, the orchestrator retrieves the missing-data procedure."""
    alert = "Truncated SIEM message: 'rule 7781 fired'"
    extraction = {**{k: None for k in ("timestamp", "source_ip", "destination_ip", "hostname", "username")},
                  "incident_type": "undetermined", "indicators": [], "evidence": ["rule 7781 fired"],
                  "missing_information": ["hostname", "user", "raw event"], "alert_confidence": "low",
                  "observed_impact": "none", "privileged_account": False}
    draft = {**GOOD_DRAFT, "recommended_actions": [{"action": "Request the raw event from the log owner.",
                                                    "citation_ids": ["PB-014"], "requires_approval": True}],
             "cited_doc_ids": ["PB-014"], "confidence": "low"}
    llm = ScriptedLLM([text(extraction), text("Not enough data to investigate."), text(draft)])
    r = make_client(offline_settings, llm).post("/api/analyze", json={"content": alert})
    assert r.status_code == 200, r.text
    body = r.json()
    searches = [s["arguments"]["query"] for s in body["agent_trace"]["steps"]
                if s["kind"] == "enforced_tool_call" and s["tool"] == "search_playbooks"]
    assert any(q.startswith("insufficient evidence") for q in searches)
    assert "PB-014" in {h["doc_id"] for h in body["retrieved"]}
    assert body["report"]["incident_type"] == "undetermined" and body["report"]["requires_human_review"]


def test_extraction_prompt_defines_severity_factors():
    from app.llm.prompts import EXTRACTION_SYSTEM, FACTOR_RUBRIC
    assert FACTOR_RUBRIC in EXTRACTION_SYSTEM
    for term in ("evidence_kind", "specific_telemetry", "observed_impact", "confirmed_limited", "lowers impact"):
        assert term in FACTOR_RUBRIC


def test_abstained_agent_search_triggers_fallback_search(offline_settings):
    """Agent searched, but its terse query passed no threshold: orchestrator retries with label + evidence."""
    llm = ScriptedLLM([text(GOOD_EXTRACTION), tool_call("search_playbooks", {"query": "zzqx qqzz"}),
                       text("Nothing found."), text(GOOD_DRAFT)])
    r = make_client(offline_settings, llm).post("/api/analyze", json={"content": BRUTE_FORCE_ALERT})
    assert r.status_code == 200, r.text
    body = r.json()
    enforced = [s for s in body["agent_trace"]["steps"]
                if s["kind"] == "enforced_tool_call" and s["tool"] == "search_playbooks"]
    assert len(enforced) == 1 and enforced[0]["arguments"]["query"].startswith("brute force")
    assert "PB-004" in {h["doc_id"] for h in body["retrieved"]}


def test_label_only_search_when_every_search_abstains(offline_settings):
    """If the label + evidence query also abstains, the incident label alone is searched last."""
    app = create_app(offline_settings, llm=ScriptedLLM([
        text(GOOD_EXTRACTION), tool_call("search_playbooks", {"query": "zzqx qqzz"}), text("Nothing."),
        text(GOOD_DRAFT)]))
    retriever = app.state.container.analysis.retriever
    real_search = retriever.search

    def strict_search(query, **kw):  # simulate a threshold that only the bare label clears
        res = real_search(query, **kw)
        return res if query == "brute force" else dataclasses.replace(res, hits=[], abstained=True)

    retriever.search = strict_search
    body = TestClient(app).post("/api/analyze", json={"content": BRUTE_FORCE_ALERT}).json()
    queries = [s["arguments"]["query"] for s in body["agent_trace"]["steps"]
               if s["kind"] == "enforced_tool_call" and s["tool"] == "search_playbooks"]
    assert queries[0].startswith("brute force:") and queries[-1] == "brute force"
    assert "PB-004" in {h["doc_id"] for h in body["retrieved"]}


def test_prompt_injection_alert_is_flagged(offline_settings):
    samples = json.loads(open("data/synthetic/sample_alerts.json", encoding="utf-8").read())["samples"]
    alert = next(s for s in samples if s["id"] == "prompt-injection")["content"]
    extraction = {**GOOD_EXTRACTION, "hostname": "LAB-TEST-07", "source_ip": "198.51.100.23",
                  "username": "admin", "timestamp": None, "evidence": ['"failed_count": 212'],
                  "indicators": ["198.51.100.23"]}
    llm = ScriptedLLM([text(extraction), tool_call("run_shell", {"cmd": "rm -rf /"}), text("done"),
                       text(GOOD_DRAFT)])
    r = make_client(offline_settings, llm).post("/api/analyze", json={"content": alert})
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    assert "possible prompt injection in input" in rep["review_reasons"]
    steps = r.json()["agent_trace"]["steps"]
    assert steps[0]["kind"] == "tool_error" and "unknown tool" in steps[0]["error"]


def test_extraction_failure_returns_502(offline_settings):
    llm = ScriptedLLM([text("nonsense")] * 3)
    r = make_client(offline_settings, llm).post("/api/analyze", json={"content": BRUTE_FORCE_ALERT})
    assert r.status_code == 502 and r.json()["detail"]["stage"] == "extraction"


def test_analyze_without_llm_config_returns_503(offline_settings):
    r = make_client(offline_settings).post("/api/analyze", json={"content": "alert"})
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]["error"]


@pytest.mark.parametrize("payload", [{}, {"content": ""}, {"content": "x", "format": "xml"},
                                     {"content": "x", "unexpected": 1}])
def test_analyze_input_validation(offline_settings, payload):
    assert make_client(offline_settings).post("/api/analyze", json=payload).status_code == 422


def test_read_only_endpoints(offline_settings):
    c = make_client(offline_settings)
    h = c.get("/api/health").json()
    assert h["status"] == "ok" and h["llm_configured"] is False and h["model"] == "gemma-4-E4B-it"
    assert h["documents"] == 19
    assert len(c.get("/api/samples").json()) >= 10
    assert len(c.get("/api/playbooks").json()) == 19
    assert c.get("/api/playbooks/PB-002").json()["title"] == "Incident Severity Scoring Matrix"
    s = c.post("/api/search", json={"query": "password spraying against many accounts"}).json()
    assert s["hits"][0]["doc_id"] == "PB-004"
    assert c.post("/api/search", json={"query": "chocolate cake recipe please"}).json()["abstained"] is True
    sev = c.post("/api/severity", json={"hostname": "HQ-DC01", "alert_confidence": "high",
                                        "observed_impact": "suspected", "privileged_account": True}).json()
    assert sev["severity"] == "Critical"
    assert c.get("/api/history", params={"incident_type": "phishing"}).json()[0]["case_id"] == "INC-2026-0918"
    assert "retrieval" in c.get("/api/eval/summary").json()
    assert c.get("/api/assets").status_code == 200


@pytest.mark.parametrize("path,codes", [
    ("/api/playbooks/..%2F..%2F.env", {400, 404}),  # router may not match the decoded slash at all
    ("/api/playbooks/..%2Fpyproject.toml", {400, 404}),
    ("/api/playbooks/PB-999", {404}), ("/api/playbooks/..", {400, 404}),
    ("/api/analyses/1%20OR%201=1", {400}), ("/api/analyses/SAI-20260101-ABCDEF", {404}),
    ("/api/history?hostname=..%2Fetc", {422}), ("/api/history?incident_type=drop_tables", {422}),
])
def test_traversal_and_injection_inputs_rejected(offline_settings, path, codes):
    r = make_client(offline_settings).get(path)
    assert r.status_code in codes
    assert "OPENAI" not in r.text and "[project]" not in r.text


def test_security_headers_and_static_ui(offline_settings):
    c = make_client(offline_settings)
    r = c.get("/")
    assert r.status_code == 200 and "SentinelAI" in r.text
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert c.get("/static/app.js").status_code == 200
