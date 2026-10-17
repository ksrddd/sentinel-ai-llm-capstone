"""Build the persistent local index: python -m scripts.ingest [--chunking section] [--backend sbert|lsa]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings  # noqa: E402
from app.rag.corpus import load_corpus  # noqa: E402
from app.rag.index import build_index, index_path  # noqa: E402


def main() -> None:
    s = Settings.from_env()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chunking", default=s.chunking, choices=["fixed", "section"])
    p.add_argument("--backend", default=s.dense_backend, choices=["lsa", "sbert"])
    args = p.parse_args()
    docs = load_corpus(s.corpus_dir)
    out = index_path(s.index_dir, args.chunking, args.backend)
    manifest = build_index(docs, args.chunking, args.backend, out)
    print(f"Ingested {len(docs)} documents -> {out.relative_to(ROOT)}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
