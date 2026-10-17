"""Deterministic severity policy (mirrors corpus document PB-002).

The LLM supplies only qualitative inputs (confidence, impact, privileged). The asset tier
is looked up from the asset catalogue, never taken from the model or the alert.
"""

from __future__ import annotations

from app.repositories.assets import AssetRepository
from app.schemas.report import SeverityAssessment

TIER_POINTS = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CONFIDENCE_POINTS = {"low": 1, "medium": 2, "high": 3}
IMPACT_POINTS = {"none": 0, "suspected": 1, "confirmed_limited": 2, "confirmed_widespread": 3}
PRIVILEGED_BONUS = 2
UNKNOWN_TIER = "medium"

# (inclusive lower bound, level), checked from highest to lowest
BANDS = ((11, "Critical"), (9, "High"), (7, "Medium"), (5, "Low"), (0, "Informational"))


def band_for(score: int) -> str:
    for lower, level in BANDS:
        if score >= lower:
            return level
    return "Informational"


def score_factors(tier: str, alert_confidence: str, observed_impact: str, privileged_account: bool) -> int:
    if tier not in TIER_POINTS:
        raise ValueError(f"unknown tier {tier!r}")
    if alert_confidence not in CONFIDENCE_POINTS:
        raise ValueError(f"unknown confidence {alert_confidence!r}")
    if observed_impact not in IMPACT_POINTS:
        raise ValueError(f"unknown impact {observed_impact!r}")
    return (TIER_POINTS[tier] + CONFIDENCE_POINTS[alert_confidence]
            + 2 * IMPACT_POINTS[observed_impact] + (PRIVILEGED_BONUS if privileged_account else 0))


class SeverityService:
    def __init__(self, assets: AssetRepository) -> None:
        self.assets = assets

    def assess(self, hostname: str | None, alert_confidence: str, observed_impact: str,
               privileged_account: bool) -> SeverityAssessment:
        asset = self.assets.get(hostname) if hostname else None
        tier = asset["tier"] if asset else UNKNOWN_TIER
        score = score_factors(tier, alert_confidence, observed_impact, privileged_account)
        level = band_for(score)
        parts = [
            f"asset tier {tier} ({TIER_POINTS[tier]})" + ("" if asset else " [unknown asset, default]"),
            f"confidence {alert_confidence} ({CONFIDENCE_POINTS[alert_confidence]})",
            f"impact {observed_impact} (2 x {IMPACT_POINTS[observed_impact]})",
            f"privileged bonus {PRIVILEGED_BONUS if privileged_account else 0}",
        ]
        return SeverityAssessment(
            severity=level, score=score, asset_tier=tier, asset_known=asset is not None,
            factors={"hostname": hostname, "asset_tier": tier, "alert_confidence": alert_confidence,
                     "observed_impact": observed_impact, "privileged_account": privileged_account},
            explanation=f"score {score} = " + " + ".join(parts) + f" -> {level} (PB-002 bands)",
        )
