"""Builds the application object graph once at startup (simple dependency container)."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, replace

from app.core.config import (
    FALLBACK_CHUNKING,
    FALLBACK_MIN_SCORE,
    FALLBACK_RETRIEVER,
    MAX_CONCURRENT_ANALYSES,
    ROOT_DIR,
    Settings,
)
from app.llm.client import ChatModel, OpenAIChatModel
from app.rag.corpus import Document
from app.rag.index import load_retriever
from app.rag.retriever import Retriever
from app.repositories.assets import AssetRepository
from app.repositories.incidents import IncidentRepository
from app.services.analysis import AnalysisService
from app.services.severity import SeverityService

log = logging.getLogger("sentinel.container")


@dataclass
class Container:
    settings: Settings
    llm: ChatModel | None
    retriever: Retriever
    documents: dict[str, Document]
    assets: AssetRepository
    incidents: IncidentRepository
    severity: SeverityService
    analysis: AnalysisService
    samples: list[dict]
    analysis_slots: threading.BoundedSemaphore


def _sbert_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def build_container(settings: Settings, llm: ChatModel | None = None) -> Container:
    if settings.retriever != "bm25" and settings.dense_backend == "sbert" and not _sbert_available():
        log.warning("sentence-transformers not installed; falling back to %s-%s retrieval "
                    "(install with: pip install -e .[neural])", FALLBACK_RETRIEVER, FALLBACK_CHUNKING)
        settings = replace(settings, retriever=FALLBACK_RETRIEVER, chunking=FALLBACK_CHUNKING,
                           min_score=FALLBACK_MIN_SCORE, retrieval_fallback=True)
    retriever, docs = load_retriever(settings.corpus_dir, settings.index_dir, method=settings.retriever,
                                     chunking=settings.chunking, backend=settings.dense_backend,
                                     alpha=settings.hybrid_alpha, min_score=settings.min_score)
    if llm is None and settings.llm_configured:
        llm = OpenAIChatModel(settings)
    assets = AssetRepository(settings.synthetic_dir / "assets.json")
    incidents = IncidentRepository(settings.db_path, settings.synthetic_dir / "incident_history.jsonl")
    severity = SeverityService(assets)
    samples = json.loads((settings.synthetic_dir / "sample_alerts.json").read_text(encoding="utf-8"))["samples"]
    return Container(settings, llm, retriever, {d.doc_id: d for d in docs}, assets, incidents, severity,
                     AnalysisService(settings, llm, retriever, severity, incidents), samples,
                     threading.BoundedSemaphore(MAX_CONCURRENT_ANALYSES))


EVAL_SUMMARY = ROOT_DIR / "eval" / "results" / "retrieval_summary.json"
EVAL_RUNS = ROOT_DIR / "eval" / "results" / "retrieval_runs.json"
E2E_SUMMARY =ROOT_DIR / "eval" / "results" / "e2e_summary.json"
