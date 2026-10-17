"""Environment-based configuration.

Secrets are read only from environment variables (optionally loaded from a local,
git-ignored ``.env`` file). Nothing in this module logs or returns the API key.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

REQUIRED_MODEL = "gemma-4-E4B-it"
PLACEHOLDER_MARK = "replace-with"  # marker used by .env.example values

# Request limits (OWASP API4: unrestricted resource consumption)
MAX_REQUEST_BYTES = 64 * 1024
MAX_CONCURRENT_ANALYSES = 2

# Retrieval defaults. These values were selected on the *development* split by
# ``python -m eval.run_retrieval_eval`` and are written to
# ``eval/results/selected_config.json``; ``tests/test_config.py`` asserts they match.
DEFAULT_RETRIEVER = "hybrid"
DEFAULT_DENSE_BACKEND = "sbert"
DEFAULT_CHUNKING = "section"
DEFAULT_HYBRID_ALPHA = 0.3
DEFAULT_MIN_SCORE = 0.316955
# Used when the optional sentence-transformers dependency is missing: the best
# non-neural configuration on the dev split (bm25-section) with its own dev-tuned threshold.
FALLBACK_RETRIEVER = "bm25"
FALLBACK_CHUNKING = "section"
FALLBACK_MIN_SCORE = 4.220667


class MissingConfigError(RuntimeError):
    """Raised when a feature needs configuration that is not present."""


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader: sets variables that are not already in the environment."""
    env_path = path or ROOT_DIR / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] in ('"', "'") and value[:1] in value[1:]:
            value = value[1:value.index(value[0], 1)]  # quoted: keep everything inside the quotes
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()  # unquoted: drop inline comment
        if key and key not in os.environ:
            os.environ[key] = value


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError as exc:
        raise MissingConfigError(f"{name} must be a number") from exc


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError as exc:
        raise MissingConfigError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = field(default=None, repr=False)
    openai_base_url: str | None = None
    model: str = REQUIRED_MODEL
    temperature: float = 0.0
    llm_timeout_s: float = 60.0
    agent_max_steps: int = 6
    agent_timeout_s: float = 150.0
    agent_tool_mode: str = "auto"  # auto | native | json
    retriever: str = DEFAULT_RETRIEVER
    dense_backend: str = DEFAULT_DENSE_BACKEND
    chunking: str = DEFAULT_CHUNKING
    hybrid_alpha: float = DEFAULT_HYBRID_ALPHA
    min_score: float = DEFAULT_MIN_SCORE
    top_k: int = 3
    retrieval_fallback: bool = False
    corpus_dir: Path = ROOT_DIR / "corpus" / "raw"
    synthetic_dir: Path = ROOT_DIR / "data" / "synthetic"
    index_dir: Path = ROOT_DIR / "data" / "index"
    db_path: Path = ROOT_DIR / "data" / "sentinel.db"

    def require_llm(self) -> None:
        missing = [n for n, v in (("OPENAI_API_KEY", self.openai_api_key),
                                  ("OPENAI_BASE_URL", self.openai_base_url)) if not v]
        if missing:
            raise MissingConfigError(
                "LLM proxy is not configured; set " + " and ".join(missing) + " (see .env.example)"
            )
        placeholders = [n for n, v in (("OPENAI_API_KEY", self.openai_api_key),
                                       ("OPENAI_BASE_URL", self.openai_base_url)) if PLACEHOLDER_MARK in (v or "")]
        if placeholders:
            raise MissingConfigError(
                ", ".join(placeholders) + ": still the .env.example placeholder. "
                "Put the real class proxy values into .env, then save the file.")

    @property
    def llm_configured(self) -> bool:
        try:
            self.require_llm()
        except MissingConfigError:
            return False
        return True

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        mode = os.environ.get("SENTINEL_AGENT_TOOL_MODE", "auto")
        if mode not in {"auto", "native", "json"}:
            raise MissingConfigError("SENTINEL_AGENT_TOOL_MODE must be auto, native or json")
        retriever = os.environ.get("SENTINEL_RETRIEVER", DEFAULT_RETRIEVER)
        if retriever not in {"bm25", "dense", "hybrid"}:
            raise MissingConfigError("SENTINEL_RETRIEVER must be bm25, dense or hybrid")
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
            openai_base_url=os.environ.get("OPENAI_BASE_URL") or None,
            model=os.environ.get("SENTINEL_MODEL", REQUIRED_MODEL),
            temperature=_float("SENTINEL_TEMPERATURE", 0.0),
            llm_timeout_s=_float("SENTINEL_LLM_TIMEOUT_S", 60.0),
            agent_max_steps=_int("SENTINEL_AGENT_MAX_STEPS", 6),
            agent_timeout_s=_float("SENTINEL_AGENT_TIMEOUT_S", 150.0),
            agent_tool_mode=mode,
            retriever=retriever,
            dense_backend=os.environ.get("SENTINEL_DENSE_BACKEND", DEFAULT_DENSE_BACKEND),
            chunking=os.environ.get("SENTINEL_CHUNKING", DEFAULT_CHUNKING),
            hybrid_alpha=_float("SENTINEL_HYBRID_ALPHA", DEFAULT_HYBRID_ALPHA),
            min_score=_float("SENTINEL_MIN_SCORE", DEFAULT_MIN_SCORE),
            top_k=_int("SENTINEL_TOP_K", 3),
            db_path=Path(os.environ.get("SENTINEL_DB_PATH", ROOT_DIR / "data" / "sentinel.db")),
        )
