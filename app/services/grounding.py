"""Anti-fabrication checks applied to LLM output, plus prompt-injection detection.

The LLM extraction is treated as a *claim*. A value survives only if it literally
appears in the raw alert text. Dropped values are reported as limitations.
"""

from __future__ import annotations

import re

from app.schemas.alert import ExtractedIncident
from app.schemas.common import HOSTNAME_PATTERN

_WS = re.compile(r"\s+")
_HOST_RE = re.compile(HOSTNAME_PATTERN)

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|rules|prompts?)",
    r"disregard (all |any )?(previous|prior|the) (instructions|rules)",
    r"you are now",
    r"system prompt",
    r"developer mode|maintenance mode",
    r"call the tool|call tool|run_shell|execute (the )?command",
    r"report (the )?severity (as )?\w+",
    r"rm -rf",
]
_INJ_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def _norm(text: str) -> str:
    return _WS.sub(" ", text.replace("\\\\", "\\").replace('\\"', '"')).strip().lower()


def detect_injection(text: str) -> list[str]:
    hits = []
    for rx in _INJ_RE:
        m = rx.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def ground_extraction(extracted: ExtractedIncident, raw_alert: str) -> tuple[ExtractedIncident, list[str]]:
    hay = _norm(raw_alert)
    dropped: list[str] = []

    def present(value: str) -> bool:
        v = _norm(value)
        return bool(v) and v in hay

    data = extracted.model_dump()
    for key in ("timestamp", "source_ip", "destination_ip", "hostname", "username"):
        val = data.get(key)
        if val is None:
            continue
        if not present(str(val)) or (key == "hostname" and not _HOST_RE.match(str(val))):
            dropped.append(f"{key}={val!r} not found verbatim in alert; removed")
            data[key] = None
    for key in ("indicators", "evidence"):
        kept = []
        for item in data[key]:
            if present(str(item)):
                kept.append(item)
            else:
                label = key[:-1] if key.endswith("s") else key
                dropped.append(f"{label} {str(item)[:60]!r} not found in alert; removed")
        data[key] = kept
    return ExtractedIncident.model_validate(data), dropped
