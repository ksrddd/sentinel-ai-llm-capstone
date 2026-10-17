"""Read-only synthetic asset catalogue."""

from __future__ import annotations

import json
from pathlib import Path


class AssetRepository:
    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self._by_host = {a["hostname"].upper(): a for a in data["assets"]}

    def get(self, hostname: str) -> dict | None:
        return self._by_host.get(hostname.strip().upper())

    def all(self) -> list[dict]:
        return list(self._by_host.values())
