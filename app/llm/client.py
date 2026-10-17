"""LLM adapter: the only module that talks to the model.

Uses the official OpenAI Python SDK against the class OpenAI-compatible proxy
(``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``) with the required ``gemma-4-E4B-it`` model.
Tests inject a scripted fake that implements the same ``chat`` method.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import Settings

_KEY_LIKE = re.compile(r"\b(sk|ghp|gho|xox[abp])[-_][A-Za-z0-9*_\-]{6,}")


def redact(text: str, secrets: tuple[str | None, ...] = ()) -> str:
    """Remove configured secrets and key-like tokens from text that may reach logs or API clients."""
    for s in secrets:
        if s and len(s) >= 6:
            text = text.replace(s, "[REDACTED]")
    return _KEY_LIKE.sub("[REDACTED]", text)


class LLMError(RuntimeError):
    """Model call failed (network, auth, proxy error). Messages are redacted before raising."""


class ToolsUnsupportedError(LLMError):
    """The proxy/model rejected native tool definitions."""


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments_json: str


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str | None = None


class ChatModel(Protocol):
    model: str

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None,
             json_mode: bool = False) -> ChatResult: ...


class OpenAIChatModel:
    def __init__(self, settings: Settings) -> None:
        settings.require_llm()
        from openai import OpenAI

        # Equivalent to OpenAI() reading OPENAI_API_KEY / OPENAI_BASE_URL from the environment;
        # passed explicitly so a .env file loaded by Settings is honoured.
        self._client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url,
                              timeout=settings.llm_timeout_s, max_retries=1)
        self.model = settings.model
        self.temperature = settings.temperature
        self._secrets = (settings.openai_api_key,)

    def _err(self, exc: Exception) -> str:
        return redact(f"{type(exc).__name__}: {str(exc)[:300]}", self._secrets)

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None,
             json_mode: bool = False) -> ChatResult:
        import openai

        kwargs: dict[str, Any] = {"model": self.model, "messages": messages,
                                  "temperature": self.temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except openai.BadRequestError as exc:
            if tools:
                raise ToolsUnsupportedError(self._err(exc)) from exc
            if json_mode:  # some proxies reject response_format; retry once without it
                kwargs.pop("response_format", None)
                try:
                    resp = self._client.chat.completions.create(**kwargs)
                except openai.OpenAIError as exc2:
                    raise LLMError(self._err(exc2)) from exc2
            else:
                raise LLMError(self._err(exc)) from exc
        except openai.OpenAIError as exc:
            raise LLMError(self._err(exc)) from exc
        if not resp.choices:
            raise LLMError("model returned no choices")
        choice = resp.choices[0]
        calls = [
            ToolCallRequest(id=tc.id or f"call_{i}", name=tc.function.name,
                            arguments_json=tc.function.arguments or "{}")
            for i, tc in enumerate(choice.message.tool_calls or [])
            if getattr(tc, "function", None) is not None
        ]
        return ChatResult(content=choice.message.content, tool_calls=calls,
                          finish_reason=choice.finish_reason)


def assistant_tool_call_message(result: ChatResult) -> dict[str, Any]:
    """Re-serialise an assistant turn containing native tool calls for the next request."""
    return {
        "role": "assistant",
        "content": result.content or "",
        "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments_json}}
            for c in result.tool_calls
        ],
    }


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)
