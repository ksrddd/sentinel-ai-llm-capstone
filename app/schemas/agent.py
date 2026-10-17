"""Agent trace schemas and tool argument models (the allow-listed tool contract)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import HOSTNAME_PATTERN, Confidence, Impact, IncidentType


class SearchPlaybooksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., min_length=3, max_length=500, description="Natural-language search query")
    top_k: int = Field(3, ge=1, le=5, description="Number of documents to return")


class CalculateSeverityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hostname: str | None = Field(None, pattern=HOSTNAME_PATTERN,
                                 description="Affected hostname exactly as it appears in the alert, or null")
    alert_confidence: Confidence = Field(..., description="Confidence that the alert reflects real activity")
    observed_impact: Impact = Field(..., description="Impact observed in the evidence")
    privileged_account: bool = Field(False, description="True if an administrator/privileged identity is involved")


class LookupHistoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hostname: str | None = Field(None, pattern=HOSTNAME_PATTERN)
    incident_type: IncidentType | None = None
    limit: int = Field(5, ge=1, le=10)


class AgentStep(BaseModel):
    step: int
    kind: Literal["tool_call", "tool_error", "model_error", "final", "enforced_tool_call"]
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result_summary: str | None = None
    error: str | None = None
    duration_ms: int = 0


class AgentTrace(BaseModel):
    mode: Literal["native", "json", "none"]
    steps: list[AgentStep] = Field(default_factory=list)
    stop_reason: Literal["completed", "max_steps", "timeout", "repeated_errors", "llm_error"]
    final_message: str | None = None
    tools_used: list[str] = Field(default_factory=list)
