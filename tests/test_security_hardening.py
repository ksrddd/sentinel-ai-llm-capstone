"""Regression tests for the OWASP recheck (placeholders, redaction, resource limits, CSP scoping)."""

import threading

import pytest
from conftest import BRUTE_FORCE_ALERT
from fastapi.testclient import TestClient

from app.core.config import MAX_REQUEST_BYTES, MissingConfigError, Settings
from app.llm.client import redact
from app.main import create_app


@pytest.mark.parametrize("key,url", [
    ("replace-with-your-class-proxy-key", "https://real.example/v1"),
    ("sk-real-looking-key-123456", "https://replace-with-class-proxy-host/v1"),
])
def test_placeholder_config_rejected(key, url):
    s = Settings(openai_api_key=key, openai_base_url=url)
    assert s.llm_configured is False
    with pytest.raises(MissingConfigError, match="placeholder"):
        s.require_llm()


def test_real_looking_config_accepted():
    assert Settings(openai_api_key="sk-abcdefgh", openai_base_url="https://proxy.example/v1").llm_configured


@pytest.mark.parametrize("text", [
    "Incorrect API key provided: sk-proj-AbC123***xyz9",
    "token ghp_abcdefghijklmnopqrstuvwxyz0123 leaked",
])
def test_key_like_tokens_redacted(text):
    out = redact(text)
    assert "[REDACTED]" in out and "sk-proj" not in out and "ghp_abc" not in out


def test_configured_secret_redacted_even_without_prefix():
    assert redact("auth failed for key Zq9-secret-value!", ("Zq9-secret-value",)) == \
        "auth failed for key [REDACTED]!"


def test_oversized_body_rejected_before_parsing(offline_settings):
    c = TestClient(create_app(offline_settings))
    big = b'{"query": "' + b"a" * (MAX_REQUEST_BYTES + 10) + b'"}'
    r = c.post("/api/search", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_chunked_oversized_body_rejected(offline_settings):
    c = TestClient(create_app(offline_settings))

    def gen():
        for _ in range(20):
            yield b"x" * 8192  # 160 KiB streamed without Content-Length
    r = c.post("/api/search", content=gen(), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_normal_body_still_accepted(offline_settings):
    c = TestClient(create_app(offline_settings))
    assert c.post("/api/search", json={"query": "password spraying"}).status_code == 200


def test_concurrent_analysis_cap_returns_429(offline_settings):
    app = create_app(offline_settings)
    slots: threading.BoundedSemaphore = app.state.container.analysis_slots
    held = 0
    while slots.acquire(blocking=False):
        held += 1
    try:
        r = TestClient(app).post("/api/analyze", json={"content": BRUTE_FORCE_ALERT})
        assert r.status_code == 429 and r.headers["Retry-After"] == "10"
    finally:
        for _ in range(held):
            slots.release()
    # slot released after a normal (here: 503 unconfigured) request
    assert TestClient(app).post("/api/analyze", json={"content": "x"}).status_code == 503
    assert TestClient(app).post("/api/analyze", json={"content": "x"}).status_code == 503


def test_docs_csp_is_scoped(offline_settings):
    c = TestClient(create_app(offline_settings))
    docs = c.get("/docs").headers["Content-Security-Policy"]
    ui = c.get("/").headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in docs
    assert "unsafe-inline" not in ui.split("script-src", 1)[1].split(";")[0]
    assert c.get("/api/health").headers["Cache-Control"] == "no-store"
