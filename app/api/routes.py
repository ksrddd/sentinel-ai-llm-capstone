"""HTTP layer: request validation and mapping service results/errors to responses."""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import MissingConfigError
from app.core.container import E2E_SUMMARY, EVAL_RUNS, EVAL_SUMMARY, Container
from app.llm.client import redact
from app.schemas.agent import CalculateSeverityArgs
from app.schemas.alert import AlertSubmission
from app.schemas.common import DOC_ID_PATTERN, HOSTNAME_PATTERN, IncidentType
from app.services.analysis import AnalysisError

log = logging.getLogger("sentinel.api")
router = APIRouter(prefix="/api")
_DOC_RE = re.compile(DOC_ID_PATTERN)
_INCIDENT_ID_RE = re.compile(r"^SAI-\d{8}-[0-9A-F]{6}$")


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(3, ge=1, le=5)


def _c(request: Request) -> Container:
    return request.app.state.container


@router.get("/health")
def health(request: Request) -> dict:
    c = _c(request)
    s = c.settings
    return {
        "status": "ok",
        "llm_configured": c.llm is not None,
        "model": getattr(c.llm, "model", s.model),
        "agent_tool_mode": s.agent_tool_mode,
        "retrieval": {"method": s.retriever, "chunking": s.chunking, "dense_backend": s.dense_backend,
                      "hybrid_alpha": s.hybrid_alpha, "min_score": s.min_score, "top_k": s.top_k,
                      "fallback": s.retrieval_fallback},
        "documents": len(c.documents),
        "chunks": len(c.retriever.chunks),
    }


@router.get("/samples")
def samples(request: Request) -> list[dict]:
    return _c(request).samples


@router.post("/analyze")
async def analyze(body: AlertSubmission, request: Request) -> dict:
    c = _c(request)
    # Each analysis can make up to ~12 model calls; cap concurrent runs (OWASP API4).
    if not c.analysis_slots.acquire(blocking=False):
        raise HTTPException(429, detail={"stage": "rate_limit",
                                         "error": "too many analyses in progress; retry shortly"},
                            headers={"Retry-After": "10"})
    try:
        return await run_in_threadpool(c.analysis.analyze, body)
    except MissingConfigError as exc:
        raise HTTPException(503, detail={"stage": "config", "error": str(exc)}) from exc
    except AnalysisError as exc:
        message = redact(str(exc), (c.settings.openai_api_key,))
        log.warning("analysis failed at %s: %s", exc.stage, message)
        raise HTTPException(502, detail={"stage": exc.stage, "error": message[:1000],
                                         "partial": exc.partial if exc.stage == "report" else {}}) from exc
    finally:
        c.analysis_slots.release()


@router.post("/search")
def search(body: SearchRequest, request: Request) -> dict:
    c = _c(request)
    res = c.retriever.search(body.query, k=body.top_k)
    return {"query": res.query, "method": res.method, "abstained": res.abstained,
            "top_score": res.top_score, "min_score": res.min_score,
            "hits": [h.to_dict() for h in res.hits]}


@router.post("/severity")
def severity(body: CalculateSeverityArgs, request: Request) -> dict:
    return _c(request).severity.assess(body.hostname, body.alert_confidence, body.observed_impact,
                                       body.privileged_account).model_dump()


@router.get("/playbooks")
def playbooks(request: Request) -> list[dict]:
    return [d.metadata() for d in _c(request).documents.values()]


@router.get("/playbooks/{doc_id}")
def playbook(doc_id: str, request: Request) -> dict:
    # IDs are matched against a fixed pattern and looked up in memory; never used as a file path.
    if not _DOC_RE.match(doc_id):
        raise HTTPException(400, detail="invalid document id")
    doc = _c(request).documents.get(doc_id)
    if doc is None:
        raise HTTPException(404, detail="document not found")
    return {**doc.metadata(), "content": doc.content}


@router.get("/assets")
def assets(request: Request) -> list[dict]:
    return _c(request).assets.all()


@router.get("/history")
def history(request: Request,
            hostname: str | None = Query(None, pattern=HOSTNAME_PATTERN),
            incident_type: IncidentType | None = None,
            limit: int = Query(20, ge=1, le=50)) -> list[dict]:
    return _c(request).incidents.search_history(hostname, incident_type, limit)


@router.get("/analyses")
def analyses(request: Request, limit: int = Query(25, ge=1, le=100)) -> list[dict]:
    return _c(request).incidents.list_analyses(limit)


@router.get("/analyses/{incident_id}")
def analysis(incident_id: str, request: Request) -> dict:
    if not _INCIDENT_ID_RE.match(incident_id):
        raise HTTPException(400, detail="invalid incident id")
    found = _c(request).incidents.get_analysis(incident_id)
    if found is None:
        raise HTTPException(404, detail="analysis not found")
    return found


@router.get("/eval/summary")
def eval_summary() -> dict:
    out: dict = {"retrieval": None, "runs": None, "e2e": None}
    if EVAL_SUMMARY.is_file():
        out["retrieval"] = json.loads(EVAL_SUMMARY.read_text(encoding="utf-8"))
    if EVAL_RUNS.is_file():
        out["runs"] = json.loads(EVAL_RUNS.read_text(encoding="utf-8"))["runs"]
    if E2E_SUMMARY.is_file():
        out["e2e"] = json.loads(E2E_SUMMARY.read_text(encoding="utf-8"))
    return out
