"""Live tests against the class proxy. Opt-in: ``pytest -m live`` with OPENAI_* variables set."""

import json

import pytest

from app.core.config import ROOT_DIR, Settings

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live_settings(tmp_path_factory):
    s = Settings.from_env()
    if not s.llm_configured:
        pytest.skip("OPENAI_API_KEY / OPENAI_BASE_URL not set")
    from dataclasses import replace
    return replace(s, db_path=tmp_path_factory.mktemp("live") / "live.db")


def test_live_chat_roundtrip(live_settings):
    from app.llm.client import OpenAIChatModel
    out = OpenAIChatModel(live_settings).chat([{"role": "user", "content": "Reply with the word OK."}])
    assert out.content and "ok" in out.content.lower()


def test_live_end_to_end_analysis(live_settings):
    from fastapi.testclient import TestClient

    from app.main import create_app
    samples = json.loads((ROOT_DIR / "data/synthetic/sample_alerts.json").read_text(encoding="utf-8"))["samples"]
    client = TestClient(create_app(live_settings))
    r = client.post("/api/analyze", json={"content": samples[0]["content"]})
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    retrieved = {h["doc_id"] for h in r.json()["retrieved"]}
    assert all(c["doc_id"] in retrieved for c in rep["source_citations"])
