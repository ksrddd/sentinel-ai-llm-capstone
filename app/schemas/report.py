"""Incident report schemas.

The report separates three kinds of content:
* ``evidence``            - observed facts copied verbatim from the alert (grounded),
* ``interpretation``      - the model's reading of those facts,
* ``recommended_actions`` - suggested next steps, each tied to playbook citations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import DOC_ID_PATTERN, Confidence, IncidentType, SeverityLevel


class Citation(BaseModel):
    doc_id: str = Field(..., pattern=DOC_ID_PATTERN)
    title: str
    version: str
    chunk_id: str | None = None
    excerpt: str | None = None


class RecommendedAction(BaseModel):
    action: str = Field(..., min_length=3, max_length=400)
    citation_ids: list[str] = Field(default_factory=list)
    requires_approval: bool = True

    @field_validator("citation_ids", mode="before")
    @classmethod
    def coerce_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value or []


class ReportDraft(BaseModel):
    """What the LLM is allowed to write. Severity, assets and evidence are NOT in here."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(..., min_length=10, max_length=1500)
    interpretation: str = Field(..., min_length=5, max_length=1500)
    confidence: Confidence
    recommended_actions: list[RecommendedAction] = Field(..., min_length=1, max_length=8)
    cited_doc_ids: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("cited_doc_ids", "limitations", mode="before")
    @classmethod
    def coerce_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value or []


class SeverityAssessment(BaseModel):
    severity: SeverityLevel
    score: int
    factors: dict[str, Any]
    asset_tier: str
    asset_known: bool
    policy_doc_id: str = "PB-002"
    explanation: str


class IncidentReport(BaseModel):
    incident_id: str
    incident_type: IncidentType
    severity: SeverityLevel
    severity_assessment: SeverityAssessment
    confidence: Confidence
    summary: str
    interpretation: str
    affected_assets: list[str]
    indicators: list[str]
    evidence: list[str]
    recommended_actions: list[RecommendedAction]
    source_citations: list[Citation]
    limitations: list[str]
    requires_human_review: bool
    review_reasons: list[str] = Field(default_factory=list)
