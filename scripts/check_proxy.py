"""Probe the class proxy for features the app depends on.

python -m scripts.check_proxy  ->  writes eval/results/proxy_compat.json

Checks: model listing, plain chat at temperature 0, JSON response_format, native tool calling.
The API key is never printed or written.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import MissingConfigError, Settings  # noqa: E402
from app.llm.client import redact  # noqa: E402


def main() -> int:
    s = Settings.from_env()
    try:
        s.require_llm()
    except MissingConfigError as exc:
        print(f"PENDING: {exc}")
        return 2
    from openai import OpenAI

    client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url, timeout=s.llm_timeout_s)
    host = urlparse(s.openai_base_url or "").hostname
    print(f"Checking {s.model} at host {host} (key not shown)")
    report: dict = {"checked_at": datetime.now(UTC).isoformat(timespec="seconds"), "model": s.model}

    def probe(name: str, fn) -> None:
        try:
            report[name] = {"ok": True, **(fn() or {})}
        except Exception as exc:  # noqa: BLE001 - report every failure mode
            cause = exc.__cause__ or exc.__context__
            detail = f"{type(exc).__name__}: {str(exc)[:300]}"
            if cause is not None:  # e.g. the DNS/TLS error behind a generic APIConnectionError
                detail += f" <- {type(cause).__name__}: {str(cause)[:200]}"
            report[name] = {"ok": False, "error": redact(detail, (s.openai_api_key,))}
        print(f"{name:<14} {'OK ' if report[name]['ok'] else 'FAIL'} {report[name]}")

    probe("list_models", lambda: {"model_listed": s.model in [m.id for m in client.models.list().data]})
    msg = [{"role": "user", "content": "Reply with exactly: OK"}]
    probe("chat", lambda: {"reply": client.chat.completions.create(
        model=s.model, messages=msg, temperature=0).choices[0].message.content[:50]})
    probe("system_role", lambda: {"reply": client.chat.completions.create(
        model=s.model, temperature=0, messages=[{"role": "system", "content": "Answer in one word."}, *msg]
    ).choices[0].message.content[:50]})
    probe("json_mode", lambda: {"reply": client.chat.completions.create(
        model=s.model, temperature=0, response_format={"type": "json_object"},
        messages=[{"role": "user", "content": 'Return the JSON object {"status": "ok"}'}]
    ).choices[0].message.content[:80]})

    def tools():
        r = client.chat.completions.create(
            model=s.model, temperature=0,
            messages=[{"role": "user", "content": "What is the severity for host HQ-DC01? Use the tool."}],
            tools=[{"type": "function", "function": {
                "name": "calculate_severity", "description": "Severity lookup",
                "parameters": {"type": "object", "properties": {"hostname": {"type": "string"}},
                               "required": ["hostname"]}}}])
        calls = r.choices[0].message.tool_calls or []
        return {"tool_calls": [{"name": c.function.name, "arguments": c.function.arguments} for c in calls],
                "native_tool_call_returned": bool(calls)}

    probe("native_tools", tools)
    out = ROOT / "eval" / "results" / "proxy_compat.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"written {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
