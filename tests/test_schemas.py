import pytest
from pydantic import ValidationError

from app.schemas.agent import CalculateSeverityArgs, SearchPlaybooksArgs
from app.schemas.alert import MAX_ALERT_CHARS, AlertSubmission, ExtractedIncident
from app.schemas.report import Citation, RecommendedAction, ReportDraft


@pytest.mark.parametrize("content", ["", "   \n\t "])
def test_blank_alert_rejected(content):
    with pytest.raises(ValidationError):
        AlertSubmission(content=content)


def test_oversized_alert_rejected():
    with pytest.raises(ValidationError):
        AlertSubmission(content="x" * (MAX_ALERT_CHARS + 1))


def test_unknown_submission_field_rejected():
    with pytest.raises(ValidationError):
        AlertSubmission(content="alert", run_as_admin=True)


def test_extraction_normalises_nulls_and_lists():
    e = ExtractedIncident(incident_type="malware", hostname="unknown", source_ip="N/A",
                          indicators="abc", evidence=None)
    assert e.hostname is None and e.source_ip is None
    assert e.indicators == ["abc"] and e.evidence == []


@pytest.mark.parametrize("bad", [{"incident_type": "alien_invasion"},
                                 {"incident_type": "malware", "source_ip": "999.1.1.1"},
                                 {"incident_type": "malware", "alert_confidence": "certain"},
                                 {"incident_type": "malware", "observed_impact": "catastrophic"}])
def test_extraction_rejects_invalid_values(bad):
    with pytest.raises(ValidationError):
        ExtractedIncident(**bad)


def test_report_draft_requires_actions():
    with pytest.raises(ValidationError):
        ReportDraft(summary="A sufficiently long summary", interpretation="interp", confidence="low",
                    recommended_actions=[])


def test_action_citation_string_coerced():
    assert RecommendedAction(action="Do the thing", citation_ids="PB-001").citation_ids == ["PB-001"]


@pytest.mark.parametrize("doc_id", ["PB-1", "../etc/passwd", "PB-0001", "pb-001"])
def test_citation_doc_id_pattern(doc_id):
    with pytest.raises(ValidationError):
        Citation(doc_id=doc_id, title="t", version="1")


@pytest.mark.parametrize("args", [{"query": "ab"}, {"query": "valid query", "top_k": 0},
                                  {"query": "valid query", "top_k": 99},
                                  {"query": "valid query", "path": "/etc"}])
def test_search_args_validation(args):
    with pytest.raises(ValidationError):
        SearchPlaybooksArgs(**args)


@pytest.mark.parametrize("hostname", ["../../etc/passwd", "host;rm -rf /", "a" * 80, "$(whoami)"])
def test_severity_args_reject_unsafe_hostnames(hostname):
    with pytest.raises(ValidationError):
        CalculateSeverityArgs(hostname=hostname, alert_confidence="high", observed_impact="none")


@pytest.mark.parametrize("kind,conf", [("specific_telemetry", "high"), ("anomaly", "medium"), ("vague", "low")])
def test_alert_confidence_derived_from_evidence_kind(kind, conf):
    e = ExtractedIncident.model_validate({"incident_type": "malware", "evidence_kind": kind,
                                          "alert_confidence": "medium" if conf != "medium" else "low"})
    assert e.alert_confidence == conf


def test_alert_confidence_kept_without_evidence_kind():
    assert ExtractedIncident.model_validate({"incident_type": "malware", "alert_confidence": "high"}).alert_confidence         == "high"


@pytest.mark.parametrize("impact,expected", [("none", "confirmed_limited"), ("suspected", "confirmed_limited"),
                                             ("confirmed_widespread", "confirmed_widespread")])
def test_confirmed_outcome_only_raises_impact(impact, expected):
    e = ExtractedIncident.model_validate({"incident_type": "malware", "observed_impact": impact,
                                          "malicious_outcome_confirmed": True})
    assert e.observed_impact == expected
