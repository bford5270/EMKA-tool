"""``make index`` entry point: ingested chunk JSONL -> dense + keyword indexes."""

from __future__ import annotations

import sys

from core.config import load_config
from core.models import load_embedder
from ingest.pipeline import load_all_chunks
from retrieval.store import build_indexes


def main() -> int:
    cfg = load_config()
    chunks = load_all_chunks(cfg)
    if not chunks:
        print("No ingested chunks found under data/chunks/ — run `make ingest` first.")
        return 1
    embedder = load_embedder(cfg)
    print(f"Indexing {len(chunks)} chunks ({embedder.backend} embeddings)…")
    build_indexes(chunks, cfg, embedder)
    print(f"Done -> {cfg.data_dir / 'index'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
