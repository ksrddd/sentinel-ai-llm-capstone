"""JSON extraction from model text and bounded validate-and-repair loop."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.client import ChatModel

T = TypeVar("T", bound=BaseModel)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class StructuredOutputError(RuntimeError):
    def __init__(self, message: str, attempts: list[str]) -> None:
        super().__init__(message)
        self.attempts = attempts


def extract_json_object(text: str | None) -> dict[str, Any]:
    """Return the first JSON object found in ``text`` (handles code fences and prose)."""
    if not text:
        raise ValueError("empty response")
    candidates = [m.group(1) for m in _FENCE_RE.finditer(text)] + [text]
    for cand in candidates:
        cand = cand.strip()
        start = cand.find("{")
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(cand)):
                ch = cand[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(cand[start:i + 1])
                        except json.JSONDecodeError:
                            break
                        if isinstance(obj, dict):
                            return obj
                        break
            start = cand.find("{", start + 1)
    raise ValueError("no JSON object found in response")


def generate_validated(llm: ChatModel, messages: list[dict[str, Any]], model_cls: type[T], *,
                       max_attempts: int = 3,
                       extra_check: Callable[[T], list[str]] | None = None) -> tuple[T, int]:
    """Ask for JSON, validate with Pydantic (+ optional semantic check), repair up to ``max_attempts``.

    Returns (validated object, attempts used). Raises StructuredOutputError when repair fails;
    it never fabricates a fallback object.
    """
    convo = list(messages)
    raw_attempts: list[str] = []
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        result = llm.chat(convo, json_mode=True)
        text = result.content or ""
        raw_attempts.append(text[:2000])
        try:
            obj = model_cls.model_validate(extract_json_object(text))
            problems = extra_check(obj) if extra_check else []
            if not problems:
                return obj, attempt
            last_error = "; ".join(problems)
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)[:800]
        convo = convo + [
            {"role": "assistant", "content": text[:4000]},
            {"role": "user", "content": (
                "Your previous answer was rejected by the validator:\n" + last_error +
                "\nReturn ONLY one corrected JSON object that satisfies the schema. No prose.")},
        ]
    raise StructuredOutputError(
        f"{model_cls.__name__} failed validation after {max_attempts} attempts: {last_error}", raw_attempts)
