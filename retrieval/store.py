"""Chunk store + indexes on disk (all under data/index/, gitignored).

Three artifacts, built together by ``make index`` and read by search:

    data/index/chunks.sqlite    chunk hydration store (chunk_id -> Chunk JSON)
                                + FTS5 full-text index over embed_text
    data/index/lance/           LanceDB dense-vector table (chunk_id, vector)

Embeddings come from the configured Embedder backend; index build embeds
``chunk.embed_text`` (breadcrumb + verbatim text, per the frozen schema).
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from core.config import EmkaConfig
from core.models import Embedder
from core.schema import Chunk

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id   TEXT NOT NULL,
    json     TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    body,
    tokenize = 'porter unicode61'
);
"""

_LANCE_TABLE = "chunks"


def _index_dir(cfg: EmkaConfig) -> Path:
    return cfg.data_dir / "index"


def _sqlite_path(cfg: EmkaConfig) -> Path:
    return _index_dir(cfg) / "chunks.sqlite"


def _lance_dir(cfg: EmkaConfig) -> Path:
    return _index_dir(cfg) / "lance"


class ChunkStore:
    """Read side: hydrate chunks and run FTS queries."""

    def __init__(self, cfg: EmkaConfig):
        path = _sqlite_path(cfg)
        if not path.exists():
            raise FileNotFoundError(f"index not built: {path} (run `make index`)")
        self._conn = sqlite3.connect(str(path))

    def get(self, chunk_id: str) -> Chunk:
        row = self._conn.execute(
            "SELECT json FROM chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        if row is None:
            raise KeyError(chunk_id)
        return Chunk.from_json(row[0])

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def keyword_search(self, query: str, limit: int = 50) -> list[tuple[str, float]]:
        """FTS5 (BM25-ranked). Returns [(chunk_id, bm25_score_ascending)]."""
        terms = [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9.-]*", query) if t]
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        rows = self._conn.execute(
            "SELECT chunk_id, bm25(chunks_fts) FROM chunks_fts "
            "WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
            (match, limit),
        ).fetchall()
        return [(cid, score) for cid, score in rows]

    def close(self) -> None:
        self._conn.close()


class DenseIndex:
    """Read side: LanceDB ANN search over chunk embeddings."""

    def __init__(self, cfg: EmkaConfig, embedder: Embedder):
        import lancedb

        path = _lance_dir(cfg)
        if not path.exists():
            raise FileNotFoundError(f"dense index not built: {path} (run `make index`)")
        self._db = lancedb.connect(str(path))
        self._table = self._db.open_table(_LANCE_TABLE)
        self._embedder = embedder

    def search(self, query: str, limit: int = 50) -> list[tuple[str, float]]:
        vec = self._embedder.embed_queries([query])[0]
        rows = self._table.search(vec).metric("cosine").limit(limit).to_list()
        return [(r["chunk_id"], float(r["_distance"])) for r in rows]


def build_indexes(chunks: list[Chunk], cfg: EmkaConfig, embedder: Embedder) -> None:
    """(Re)build both indexes from scratch. Deterministic given inputs."""
    import lancedb

    index_dir = _index_dir(cfg)
    index_dir.mkdir(parents=True, exist_ok=True)

    # --- sqlite store + FTS ---
    sqlite_path = _sqlite_path(cfg)
    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(str(sqlite_path))
    conn.executescript(_SQLITE_SCHEMA)
    conn.executemany(
        "INSERT INTO chunks VALUES (?, ?, ?)",
        [(c.chunk_id, c.doc_id, c.to_json()) for c in chunks],
    )
    conn.executemany(
        "INSERT INTO chunks_fts (chunk_id, body) VALUES (?, ?)",
        [(c.chunk_id, c.embed_text) for c in chunks],
    )
    conn.commit()
    conn.close()

    # --- dense vectors ---
    vectors = embedder.embed_documents([c.embed_text for c in chunks])
    db = lancedb.connect(str(_lance_dir(cfg)))
    if _LANCE_TABLE in db.list_tables():
        db.drop_table(_LANCE_TABLE)
    db.create_table(
        _LANCE_TABLE,
        data=[
            {"chunk_id": c.chunk_id, "vector": v}
            for c, v in zip(chunks, vectors, strict=True)
        ],
    )

    meta = {"n_chunks": len(chunks), "embed_backend": embedder.backend}
    (index_dir / "index_meta.json").write_text(json.dumps(meta, indent=2))
