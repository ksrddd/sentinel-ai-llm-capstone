"""End-to-end incident analysis orchestration.

extract (LLM, validated) -> ground (drop unsupported values) -> agent (bounded tool loop)
-> enforce required tools -> draft report (LLM, validated + citation check, bounded repair)
-> assemble final report (severity/evidence/citations come from deterministic code) -> persist.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from app.agent.loop import AgentRunner
from app.agent.tools import ToolRegistry
from app.core.config import Settings
from app.llm.client import ChatModel, LLMError
from app.llm.prompts import extraction_messages, report_messages
from app.llm.structured import StructuredOutputError, generate_validated
from app.rag.retriever import Retriever
from app.repositories.incidents import IncidentRepository
from app.schemas.agent import AgentStep
from app.schemas.alert import AlertSubmission, ExtractedIncident
from app.schemas.report import Citation, IncidentReport, ReportDraft
from app.services.grounding import detect_injection, ground_extraction
from app.services.severity import SeverityService

INSUFFICIENT_EVIDENCE_QUERY = ("insufficient evidence: alert is missing host, user or source fields; "
                               "incident type cannot be determined; request the missing data")


class AnalysisError(RuntimeError):
    def __init__(self, stage: str, message: str, partial: dict | None = None) -> None:
        super().__init__(message)
        self.stage, self.partial = stage, partial or {}


def citation_problems(draft: ReportDraft, allowed: set[str]) -> list[str]:
    cited = set(draft.cited_doc_ids) | {c for a in draft.recommended_actions for c in a.citation_ids}
    bad = sorted(cited - allowed)
    problems = []
    if bad:
        problems.append(f"citations {bad} were not retrieved; allowed IDs are {sorted(allowed) or 'none'}")
    if allowed and not cited:
        problems.append("cite at least one retrieved document ID")
    return problems


class AnalysisService:
    def __init__(self, settings: Settings, llm: ChatModel | None, retriever: Retriever,
                 severity: SeverityService, incidents: IncidentRepository) -> None:
        self.settings, self.llm = settings, llm
        self.retriever, self.severity, self.incidents = retriever, severity, incidents

    def analyze(self, submission: AlertSubmission) -> dict:
        if self.llm is None:
            self.settings.require_llm()
            raise AnalysisError("config", "LLM client unavailable")
        llm = self.llm
        alert = submission.content
        timings: dict[str, int] = {}
        t0 = time.perf_counter()

        # 1. Structured extraction + grounding
        try:
            raw_extracted, extract_attempts = generate_validated(llm, extraction_messages(alert), ExtractedIncident)
        except StructuredOutputError as exc:
            raise AnalysisError("extraction", str(exc), {"raw_attempts": exc.attempts}) from exc
        except LLMError as exc:
            raise AnalysisError("extraction", str(exc)) from exc
        extracted, dropped = ground_extraction(raw_extracted, alert)
        injection = detect_injection(alert)
        timings["extraction_ms"] = int((time.perf_counter() - t0) * 1000)

        # 2. Agent loop
        t1 = time.perf_counter()
        registry = ToolRegistry(self.retriever, self.severity, self.incidents)
        runner = AgentRunner(llm, registry, max_steps=self.settings.agent_max_steps,
                             timeout_s=self.settings.agent_timeout_s, mode=self.settings.agent_tool_mode)
        trace = runner.run(alert, extracted.model_dump())

        # 3. Enforce required tools (transparently recorded as enforced steps)
        def enforce(tool: str, args: dict) -> dict:
            result = registry.execute(tool, args)
            trace.steps.append(AgentStep(step=len(trace.steps) + 1, kind="enforced_tool_call", tool=tool,
                                         arguments=args, result_summary="executed by orchestrator"))
            return result

        if "search_playbooks" not in trace.tools_used or not registry.retrieved:
            # Also when every agent search abstained: terse keyword queries often score below the
            # threshold, while the incident label plus the alert evidence is a fuller description.
            label = extracted.incident_type.replace("_", " ")
            query = f"{label}: " + "; ".join(extracted.evidence[:3] or [alert[:300]])
            enforce("search_playbooks", {"query": query[:500], "top_k": 3})
            if not registry.retrieved and extracted.incident_type != "undetermined":
                # Last resort: the incident label alone (e.g. "malware") ranks its playbook first for every type.
                enforce("search_playbooks", {"query": label, "top_k": 3})
        if extracted.incident_type == "undetermined":
            # Insufficient-evidence alerts need the procedure for missing data, not a guess at what the
            # vague text resembles; the agent's own search is driven by that vague text.
            enforce("search_playbooks", {"query": INSUFFICIENT_EVIDENCE_QUERY, "top_k": 3})
        sev_args = {"hostname": extracted.hostname, "alert_confidence": extracted.alert_confidence,
                    "observed_impact": extracted.observed_impact,
                    "privileged_account": extracted.privileged_account}
        agent_sev = registry.severity_results[-1] if registry.severity_results else None
        if agent_sev is None or agent_sev["factors"]["hostname"] != extracted.hostname or any(
                agent_sev["factors"][k] != sev_args[k] for k in ("alert_confidence", "observed_impact",
                                                                 "privileged_account")):
            severity = enforce("calculate_severity", sev_args)
            severity_note = ("Agent severity call used factors different from the grounded extraction; "
                             "authoritative severity recomputed from extraction." if agent_sev else None)
        else:
            severity, severity_note = agent_sev, None
        timings["agent_ms"] = int((time.perf_counter() - t1) * 1000)

        # 4. Report draft with citation validation and bounded repair
        t2 = time.perf_counter()
        hits = sorted(registry.retrieved.values(), key=lambda h: -h.score)[:5]
        allowed = {h.doc_id for h in hits}
        excerpts = [{"doc_id": h.doc_id, "title": h.title, "text": h.text} for h in hits]
        try:
            draft, report_attempts = generate_validated(
                llm, report_messages(alert, extracted.model_dump(), severity, excerpts, trace.final_message),
                ReportDraft, extra_check=lambda d: citation_problems(d, allowed))
        except StructuredOutputError as exc:
            raise AnalysisError("report", str(exc), {"extraction": extracted.model_dump(),
                                                     "trace": trace.model_dump(),
                                                     "raw_attempts": exc.attempts}) from exc
        except LLMError as exc:
            raise AnalysisError("report", str(exc)) from exc
        timings["report_ms"] = int((time.perf_counter() - t2) * 1000)

        # 5. Assemble final report (deterministic parts never come from the model)
        by_id = {h.doc_id: h for h in hits}
        cited = list(dict.fromkeys(draft.cited_doc_ids + [c for a in draft.recommended_actions
                                                          for c in a.citation_ids]))
        citations = [Citation(doc_id=d, title=by_id[d].title, version=by_id[d].version,
                              chunk_id=by_id[d].chunk_id, excerpt=by_id[d].text[:300]) for d in cited]
        limitations = list(draft.limitations)
        limitations += [f"Missing: {m}" for m in extracted.missing_information]
        limitations += [f"Grounding check: {d}" for d in dropped]
        if not severity["asset_known"]:
            limitations.append("Affected asset not found in catalogue; tier defaulted to medium (PB-002).")
        if severity_note:
            limitations.append(severity_note)
        if not hits:
            limitations.append("No playbook passed the retrieval relevance threshold.")
        if injection:
            limitations.append("Possible prompt-injection text in alert was ignored: " + "; ".join(injection))

        reasons = []
        if severity["severity"] in ("High", "Critical"):
            reasons.append(f"severity {severity['severity']}")
        if extracted.incident_type == "undetermined":
            reasons.append("incident type undetermined")
        if draft.confidence == "low":
            reasons.append("low model confidence")
        if extracted.missing_information:
            reasons.append("missing information")
        if dropped:
            reasons.append("ungrounded model output removed")
        if injection:
            reasons.append("possible prompt injection in input")
        if not severity["asset_known"]:
            reasons.append("unknown asset")
        if not hits:
            reasons.append("no supporting playbook retrieved")
        if trace.stop_reason != "completed":
            reasons.append(f"agent stopped: {trace.stop_reason}")

        incident_id = f"SAI-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        assets = [extracted.hostname] if extracted.hostname else []
        assets += [ip for ip in (extracted.source_ip, extracted.destination_ip) if ip]
        report = IncidentReport(
            incident_id=incident_id, incident_type=extracted.incident_type,
            severity=severity["severity"], severity_assessment=severity,
            confidence="low" if extracted.incident_type == "undetermined" else draft.confidence,
            summary=draft.summary, interpretation=draft.interpretation, affected_assets=assets,
            indicators=extracted.indicators, evidence=extracted.evidence,
            recommended_actions=draft.recommended_actions, source_citations=citations,
            limitations=limitations, requires_human_review=bool(reasons), review_reasons=reasons,
        )
        timings["total_ms"] = int((time.perf_counter() - t0) * 1000)
        payload = {
            "report": report.model_dump(),
            "extraction": extracted.model_dump(),
            "agent_trace": trace.model_dump(),
            "retrieved": [h.to_dict() for h in hits],
            "model": getattr(llm, "model", "unknown"),
            "attempts": {"extraction": extract_attempts, "report": report_attempts},
            "timings": timings,
        }
        self.incidents.save_analysis(incident_id, submission.label, report.incident_type, report.severity,
                                     report.requires_human_review, payload)
        return payload
