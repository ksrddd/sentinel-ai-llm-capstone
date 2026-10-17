from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from app.core.config import FALLBACK_MIN_SCORE, ROOT_DIR, Settings
from app.llm.client import ChatResult, ToolCallRequest
from app.rag.chunking import chunk_corpus
from app.rag.corpus import load_corpus
from app.rag.retriever import Retriever
from app.repositories.assets import AssetRepository
from app.repositories.incidents import IncidentRepository
from app.services.severity import SeverityService

CORPUS = ROOT_DIR / "corpus" / "raw"
SYNTH = ROOT_DIR / "data" / "synthetic"


class ScriptedLLM:
    """Fake ChatModel: returns queued responses in order and records every request."""

    model = "scripted-fake"

    def __init__(self, responses: list[ChatResult | Callable[[list[dict]], ChatResult] | Exception]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def chat(self, messages, *, tools=None, json_mode=False):
        self.calls.append({"messages": messages, "tools": tools, "json_mode": json_mode})
        if not self.responses:
            raise AssertionError("ScriptedLLM ran out of responses")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(messages) if callable(item) else item


def text(obj) -> ChatResult:
    return ChatResult(content=obj if isinstance(obj, str) else json.dumps(obj))


def tool_call(name: str, args: dict, call_id: str = "c1") -> ChatResult:
    return ChatResult(content=None, tool_calls=[ToolCallRequest(call_id, name, json.dumps(args))])


BRUTE_FORCE_ALERT = json.loads((SYNTH / "sample_alerts.json").read_text(encoding="utf-8"))["samples"][0]["content"]

GOOD_EXTRACTION = {
    "incident_type": "brute_force", "timestamp": "2026-10-14T03:12:44Z", "source_ip": "203.0.113.45",
    "destination_ip": None, "hostname": "WS-FIN-114", "username": "j.tan",
    "indicators": ["203.0.113.45", "AUTH-BF-020"], "evidence": ["\"failed_count\": 63"],
    "missing_information": [], "alert_confidence": "high", "observed_impact": "none",
    "privileged_account": False,
}

GOOD_DRAFT = {
    "summary": "63 failed logons for j.tan on WS-FIN-114 from 203.0.113.45 within 8 minutes, no success.",
    "interpretation": "Consistent with password guessing; no evidence of a successful compromise.",
    "confidence": "medium",
    "recommended_actions": [{"action": "Block the external source after tier-2 approval.",
                             "citation_ids": ["PB-004"], "requires_approval": True}],
    "cited_doc_ids": ["PB-004"],
    "limitations": ["Source reputation not verified."],
}


@pytest.fixture(scope="session")
def docs():
    return load_corpus(CORPUS)


@pytest.fixture(scope="session")
def bm25_retriever(docs):
    return Retriever(docs, chunk_corpus(docs, "section"), "bm25", min_score=FALLBACK_MIN_SCORE)


@pytest.fixture()
def incidents():
    return IncidentRepository(Path(":memory:"), SYNTH / "incident_history.jsonl")


@pytest.fixture(scope="session")
def severity_service():
    return SeverityService(AssetRepository(SYNTH / "assets.json"))


@pytest.fixture()
def offline_settings(tmp_path):
    return Settings(openai_api_key=None, openai_base_url=None, retriever="bm25", chunking="section",
                    min_score=FALLBACK_MIN_SCORE, db_path=tmp_path / "test.db", agent_tool_mode="auto")
