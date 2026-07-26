"""Local ingest log (SQLite). Status and hashes are recorded HERE —
never written back to the manifest xlsx."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_log (
    doc_id      TEXT NOT NULL,
    sha256      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL,
    n_chunks    INTEGER NOT NULL DEFAULT 0,
    n_pages     INTEGER NOT NULL DEFAULT 0,
    error       TEXT NOT NULL DEFAULT '',
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ingest_log_doc ON ingest_log(doc_id);
"""


class IngestLog:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)

    def record(
        self,
        doc_id: str,
        status: str,
        sha256: str = "",
        n_chunks: int = 0,
        n_pages: int = 0,
        error: str = "",
    ) -> None:
        self._conn.execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                sha256,
                status,
                n_chunks,
                n_pages,
                error,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        self._conn.commit()

    def latest(self, doc_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT doc_id, sha256, status, n_chunks, n_pages, error, ingested_at "
            "FROM ingest_log WHERE doc_id = ? ORDER BY rowid DESC LIMIT 1",
            (doc_id,),
        ).fetchone()
        if row is None:
            return None
        keys = ("doc_id", "sha256", "status", "n_chunks", "n_pages", "error", "ingested_at")
        return dict(zip(keys, row, strict=True))

    def close(self) -> None:
        self._conn.close()
