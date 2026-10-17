"""Shared enumerations and small validated types."""

from __future__ import annotations

from typing import Literal

DOC_ID_PATTERN = r"^PB-\d{3}$"
HOSTNAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,62}$"

IncidentType = Literal[
    "brute_force",
    "suspicious_login",
    "privileged_account_compromise",
    "malware",
    "suspicious_powershell",
    "command_injection",
    "unusual_outbound",
    "data_exfiltration",
    "suspicious_dns",
    "phishing",
    "false_positive",
    "undetermined",
]

INCIDENT_TYPES: tuple[str, ...] = IncidentType.__args__  # type: ignore[attr-defined]

Confidence = Literal["low", "medium", "high"]
# What kind of evidence the alert contains; alert confidence is derived from it deterministically
# (asking the model for a descriptive category avoids its tendency to hedge every confidence to "medium").
EvidenceKind = Literal["specific_telemetry", "anomaly", "vague"]
CONFIDENCE_FROM_EVIDENCE: dict[str, str] = {"specific_telemetry": "high", "anomaly": "medium", "vague": "low"}
Impact = Literal["none", "suspected", "confirmed_limited", "confirmed_widespread"]
SeverityLevel = Literal["Informational", "Low", "Medium", "High", "Critical"]
AssetTier = Literal["low", "medium", "high", "critical"]
