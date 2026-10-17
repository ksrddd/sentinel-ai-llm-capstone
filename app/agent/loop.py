"""Bounded tool-calling agent loop.

Two protocols, chosen by ``mode``:
* ``native`` - OpenAI-compatible function calling (``tools=`` / ``tool_calls``).
* ``json``   - documented text protocol: the model replies with one JSON object
               ``{"action": "call_tool", "tool": ..., "arguments": {...}}`` or
               ``{"action": "finish", "note": ...}``. This is NOT native function calling;
               it is a validated, model-selected action protocol used when the proxy
               rejects native tool definitions.
* ``auto``   - try native, fall back to json on ``ToolsUnsupportedError`` (recorded in trace).

Stop conditions: final answer, ``max_steps`` model calls, wall-clock ``timeout_s``,
``max_consecutive_errors`` invalid actions/tool errors in a row, or an LLM transport error.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from app.agent.tools import ToolError, ToolRegistry
from app.llm.client import ChatModel, LLMError, ToolsUnsupportedError, assistant_tool_call_message
from app.llm.prompts import AGENT_SYSTEM, JSON_PROTOCOL, agent_user_message
from app.llm.structured import extract_json_object
from app.schemas.agent import AgentStep, AgentTrace

MAX_CALLS_PER_TURN = 3


def _summarise(result: dict) -> str:
    if "results" in result:
        ids = [r["doc_id"] for r in result["results"]]
        return f"{len(ids)} playbook(s): {', '.join(ids)}" if ids else "abstained: no playbook above threshold"
    if "severity" in result:
        return f"{result['severity']} (score {result['score']}, tier {result['asset_tier']})"
    if "incidents" in result:
        return f"{result['count']} past incident(s)"
    return json.dumps(result)[:160]


class AgentRunner:
    def __init__(self, llm: ChatModel, registry: ToolRegistry, *, max_steps: int = 6,
                 timeout_s: float = 150.0, mode: str = "auto", max_consecutive_errors: int = 3,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        self.llm, self.registry = llm, registry
        self.max_steps, self.timeout_s = max_steps, timeout_s
        self.mode = mode
        self.max_errors = max_consecutive_errors
        self.clock = clock

    def _initial_messages(self, protocol: str, alert_text: str, extracted: dict) -> list[dict[str, Any]]:
        system = AGENT_SYSTEM
        if protocol == "json":
            system += "\n\n" + JSON_PROTOCOL + json.dumps(
                [s["function"] for s in self.registry.schemas()], indent=1)
        return [{"role": "system", "content": system},
                {"role": "user", "content": agent_user_message(alert_text, extracted)}]

    def run(self, alert_text: str, extracted: dict) -> AgentTrace:
        protocol = "json" if self.mode == "json" else "native"
        messages = self._initial_messages(protocol, alert_text, extracted)
        steps: list[AgentStep] = []
        cache: dict[str, dict] = {}
        errors = 0
        start = self.clock()

        def record(**kw: Any) -> None:
            steps.append(AgentStep(step=len(steps) + 1, **kw))

        def call_tool(name: str, args: Any) -> tuple[str, bool]:
            """Execute one tool call; returns (content for model, ok)."""
            t0 = time.perf_counter()
            key = f"{name}:{json.dumps(args, sort_keys=True) if not isinstance(args, str) else args}"
            if key in cache:
                record(kind="tool_error", tool=name, arguments=args if isinstance(args, dict) else None,
                       error="duplicate call refused (same tool and arguments already executed)")
                return json.dumps({"error": "duplicate call; use the earlier result"}), False
            try:
                result = self.registry.execute(name, args)
            except ToolError as exc:
                record(kind="tool_error", tool=name, arguments=args if isinstance(args, dict) else None,
                       error=str(exc)[:400], duration_ms=int((time.perf_counter() - t0) * 1000))
                return json.dumps({"error": str(exc)[:400]}), False
            cache[key] = result
            record(kind="tool_call", tool=name,
                   arguments=args if isinstance(args, dict) else json.loads(args or "{}"),
                   result_summary=_summarise(result), duration_ms=int((time.perf_counter() - t0) * 1000))
            return "<tool_result>\n" + json.dumps(result, default=str) + "\n</tool_result>", True

        for _ in range(self.max_steps):
            if self.clock() - start > self.timeout_s:
                return self._trace(protocol, steps, "timeout")
            try:
                result = self.llm.chat(messages, tools=self.registry.schemas() if protocol == "native" else None,
                                       json_mode=protocol == "json")
            except ToolsUnsupportedError as exc:
                if self.mode != "auto" or protocol != "native":
                    record(kind="model_error", error=f"native tools unsupported: {exc}"[:400])
                    return self._trace(protocol, steps, "llm_error")
                record(kind="model_error", error="native tool calling rejected by proxy; switching to JSON protocol")
                protocol = "json"
                messages = self._initial_messages(protocol, alert_text, extracted)
                continue
            except LLMError as exc:
                record(kind="model_error", error=str(exc)[:400])
                return self._trace(protocol, steps, "llm_error")

            if protocol == "native":
                if not result.tool_calls:
                    record(kind="final", result_summary=(result.content or "")[:300])
                    return self._trace(protocol, steps, "completed", result.content)
                calls = result.tool_calls[:MAX_CALLS_PER_TURN]
                result.tool_calls = calls
                messages.append(assistant_tool_call_message(result))
                turn_ok = False
                for c in calls:
                    content, ok = call_tool(c.name, c.arguments_json)
                    turn_ok = turn_ok or ok
                    messages.append({"role": "tool", "tool_call_id": c.id, "content": content})
                errors = 0 if turn_ok else errors + 1
            else:
                text = result.content or ""
                try:
                    action = extract_json_object(text)
                    kind = action.get("action")
                    if kind == "finish":
                        note = str(action.get("note", ""))[:2000]
                        record(kind="final", result_summary=note[:300])
                        return self._trace(protocol, steps, "completed", note)
                    if kind != "call_tool" or not isinstance(action.get("tool"), str):
                        raise ValueError('action must be "call_tool" (with "tool") or "finish"')
                except ValueError as exc:
                    errors += 1
                    record(kind="model_error", error=f"invalid action: {exc}"[:400])
                    messages += [{"role": "assistant", "content": text[:2000]},
                                 {"role": "user", "content": f"Invalid reply ({exc}). Reply with ONE JSON "
                                  "object following the protocol."}]
                    if errors >= self.max_errors:
                        return self._trace(protocol, steps, "repeated_errors")
                    continue
                content, ok = call_tool(action["tool"], action.get("arguments", {}))
                errors = 0 if ok else errors + 1
                messages += [{"role": "assistant", "content": text[:2000]},
                             {"role": "user", "content": content + "\nContinue: call another tool or finish."}]
            if errors >= self.max_errors:
                return self._trace(protocol, steps, "repeated_errors")
        return self._trace(protocol, steps, "max_steps")

    def _trace(self, protocol: str, steps: list[AgentStep], reason: str, final: str | None = None) -> AgentTrace:
        used = sorted({s.tool for s in steps if s.kind == "tool_call" and s.tool})
        return AgentTrace(mode=protocol, steps=steps, stop_reason=reason, final_message=final, tools_used=used)
