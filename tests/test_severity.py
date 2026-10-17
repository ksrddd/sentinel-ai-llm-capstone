import pytest

from app.services.severity import band_for, score_factors


@pytest.mark.parametrize("score,level", [(0, "Informational"), (4, "Informational"), (5, "Low"), (6, "Low"),
                                         (7, "Medium"), (8, "Medium"), (9, "High"), (10, "High"),
                                         (11, "Critical"), (15, "Critical")])
def test_bands(score, level):
    assert band_for(score) == level


def test_pb002_worked_example():
    # PB-002: high confidence (3) on critical DB (4) with suspected impact (2) -> 9 -> High
    assert score_factors("critical", "high", "suspected", False) == 9
    assert band_for(9) == "High"


@pytest.mark.parametrize("host,conf,impact,priv,expected", [
    ("HQ-DC01", "high", "suspected", True, "Critical"),
    ("WS-FIN-114", "high", "none", False, "Low"),
    ("LAB-TEST-07", "low", "none", False, "Informational"),
    ("DB-CUST-01", "high", "confirmed_widespread", False, "Critical"),
    ("WS-ENG-207", "high", "confirmed_limited", False, "High"),
])
def test_catalogue_driven_assessment(severity_service, host, conf, impact, priv, expected):
    assert severity_service.assess(host, conf, impact, priv).severity == expected


def test_unknown_asset_defaults_to_medium_and_is_flagged(severity_service):
    a = severity_service.assess("NOT-IN-CATALOGUE", "medium", "suspected", False)
    assert a.asset_tier == "medium" and not a.asset_known and a.score == 6
    assert "unknown asset" in a.explanation


def test_missing_hostname(severity_service):
    assert not severity_service.assess(None, "high", "none", False).asset_known


def test_hostname_lookup_case_insensitive(severity_service):
    assert severity_service.assess("hq-dc01", "low", "none", False).asset_tier == "critical"


@pytest.mark.parametrize("args", [("galactic", "high", "none", False), ("low", "sure", "none", False),
                                  ("low", "high", "huge", False)])
def test_invalid_factors_raise(args):
    with pytest.raises(ValueError):
        score_factors(*args)
