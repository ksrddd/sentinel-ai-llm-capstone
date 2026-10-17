import json

import pytest

from app.core import config
from app.core.config import ROOT_DIR, MissingConfigError, Settings


@pytest.fixture()
def clean_env(monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "SENTINEL_AGENT_TOOL_MODE", "SENTINEL_RETRIEVER",
                 "SENTINEL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda path=None: None)


def test_missing_llm_config_is_reported(clean_env):
    s = Settings.from_env()
    assert not s.llm_configured
    with pytest.raises(MissingConfigError, match="OPENAI_API_KEY and OPENAI_BASE_URL"):
        s.require_llm()


def test_partial_config_names_missing_variable(clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(MissingConfigError, match="OPENAI_BASE_URL"):
        Settings.from_env().require_llm()


def test_api_key_not_in_repr(clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-very-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://proxy.invalid/v1")
    s = Settings.from_env()
    assert s.llm_configured
    assert "sk-very-secret" not in repr(s)


def test_required_model_is_default(clean_env):
    assert Settings.from_env().model == "gemma-4-E4B-it"


@pytest.mark.parametrize("var,value", [("SENTINEL_AGENT_TOOL_MODE", "shell"), ("SENTINEL_RETRIEVER", "magic")])
def test_invalid_enum_settings_rejected(clean_env, monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    with pytest.raises(MissingConfigError):
        Settings.from_env()


def test_dotenv_strips_inline_comments_and_quotes(tmp_path, monkeypatch):
    for name in ("SENTINEL_AGENT_TOOL_MODE", "SENTINEL_MODEL", "OPENAI_BASE_URL", "X_HASH"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "# comment line\n"
        "SENTINEL_AGENT_TOOL_MODE=auto        # auto | native | json\n"
        'SENTINEL_MODEL="gemma-4-E4B-it"  # required\n'
        "OPENAI_BASE_URL=https://proxy.invalid/v1#frag\n"
        "X_HASH='a # b'\n", encoding="utf-8")
    config.load_dotenv(env)
    import os
    assert os.environ["SENTINEL_AGENT_TOOL_MODE"] == "auto"
    assert os.environ["SENTINEL_MODEL"] == "gemma-4-E4B-it"
    assert os.environ["OPENAI_BASE_URL"] == "https://proxy.invalid/v1#frag"  # '#' without space is kept
    assert os.environ["X_HASH"] == "a # b"
    for name in ("SENTINEL_AGENT_TOOL_MODE", "SENTINEL_MODEL", "OPENAI_BASE_URL", "X_HASH"):
        monkeypatch.delenv(name, raising=False)


def test_example_env_file_is_loadable(monkeypatch):
    """The committed .env.example must parse into valid settings (regression for inline comments)."""
    for line in (ROOT_DIR / ".env.example").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            monkeypatch.delenv(line.split("=", 1)[0].strip(), raising=False)
    config.load_dotenv(ROOT_DIR / ".env.example")
    s = Settings.from_env()
    assert s.agent_tool_mode == "auto" and s.model == "gemma-4-E4B-it" and s.agent_max_steps == 6
    import os
    for line in (ROOT_DIR / ".env.example").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            os.environ.pop(line.split("=", 1)[0].strip(), None)


def test_defaults_match_dev_selected_configuration():
    """Application defaults must equal the configuration selected on the dev split."""
    selected = json.loads((ROOT_DIR / "eval/results/selected_config.json").read_text(encoding="utf-8"))
    assert selected["method"] == config.DEFAULT_RETRIEVER
    assert selected["chunking"] == config.DEFAULT_CHUNKING
    assert selected["backend"] == config.DEFAULT_DENSE_BACKEND
    assert selected["alpha"] == pytest.approx(config.DEFAULT_HYBRID_ALPHA)
    assert selected["threshold"] == pytest.approx(config.DEFAULT_MIN_SCORE, abs=1e-6)


def test_fallback_matches_dev_tuned_bm25_section_run():
    runs = json.loads((ROOT_DIR / "eval/results/retrieval_runs.json").read_text(encoding="utf-8"))["runs"]
    run = next(r for r in runs if r["name"] == "bm25-section")
    assert run["threshold"] == pytest.approx(config.FALLBACK_MIN_SCORE, abs=1e-6)
