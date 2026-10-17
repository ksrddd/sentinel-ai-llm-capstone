"""Shared tokenizer for lexical and LSA retrieval (identical for baseline and candidate)."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has have how i if in into
    is it its me my no not of on or our should so some such than that the their them then there these
    they this to was we were what when where which while who why will with would you your about after
    before just only also any all more most other same very""".split()
)


def _stem(token: str) -> str:
    # Very small suffix normaliser; deterministic and dependency-free.
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]
