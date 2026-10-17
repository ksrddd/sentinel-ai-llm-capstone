"""Alert input and LLM extraction schemas."""

from __future__ import annotations

import ipaddress
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import CONFIDENCE_FROM_EVIDENCE, Confidence, EvidenceKind, Impact, IncidentType

MAX_ALERT_CHARS = 20_000


class AlertSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1, max_length=MAX_ALERT_CHARS,
                         description="Raw alert as JSON text or plain log lines (synthetic data only)")
    format: Literal["auto", "json", "text"] = "auto"
    label: str | None = Field(default=None, max_length=120)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("alert content must not be blank")
        return value


class ExtractedIncident(BaseModel):
    """Fields the LLM extracts from an alert. Every value must be grounded in the alert text."""

    model_config = ConfigDict(extra="ignore")

    incident_type: IncidentType
    timestamp: str | None = None
    source_ip: str | None = None
    destination_ip: str | None = None
    hostname: str | None = None
    username: str | None = None
    indicators: list[str] = Field(default_factory=list, max_length=25)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
    evidence_kind: EvidenceKind | None = None
    alert_confidence: Confidence = "medium"
    observed_impact: Impact = "suspected"
    privileged_account: bool = False
    malicious_outcome_confirmed: bool = False

    @model_validator(mode="after")
    def derive_confidence(self) -> ExtractedIncident:
        if self.evidence_kind is not None:
            self.alert_confidence = CONFIDENCE_FROM_EVIDENCE[self.evidence_kind]  # type: ignore[assignment]
        # A yes/no "did it actually work?" question is answered more reliably than picking an impact level;
        # it can only raise impact to confirmed_limited, never lower it.
        if self.malicious_outcome_confirmed and self.observed_impact in ("none", "suspected"):
            self.observed_impact = "confirmed_limited"
        return self

    @field_validator("source_ip", "destination_ip")
    @classmethod
    def valid_ip(cls, value: str | None) -> str | None:
        if value in (None, "", "null", "unknown", "N/A"):
            return None
        ipaddress.ip_address(value.strip())
        return value.strip()

    @field_validator("timestamp", "hostname", "username", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "unknown", "n/a"}:
            return None
        return value

    @field_validator("indicators", "evidence", "missing_information", mode="before")
    @classmethod
    def coerce_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value
