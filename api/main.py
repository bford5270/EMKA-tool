"""EMKA FastAPI service — localhost / isolated-LAN only, no external calls.

Endpoints:
    POST /query                 question -> full structured AnswerResult
    POST /corpus/refresh        maintainer: re-run manifest ingest + reindex
    POST /flag                  UI "flag this answer" -> maintainer queue
    GET  /source/{doc_id}/page/{n}   serve the source PDF (tap-to-open)
    GET  /health

Every query is logged locally (question, retrieved source ids, mode,
verification, latency) — NEVER any patient data; a persistent no-PHI notice
rides on every response. Serve with:  make serve  (binds 127.0.0.1).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.config import EmkaConfig, load_config

NO_PHI_NOTICE = (
    "EMKA is a reference system. Do not enter patient-identifying information. "
    "No patient data is stored by this service."
)

# The Swagger UI (/docs) and ReDoc (/redoc) HTML load their JS/CSS from
# cdn.jsdelivr.net — an external network reference that is both broken and
# disallowed on an air-gapped device (DESIGN.md §1). Both are disabled; the
# OpenAPI JSON schema at /openapi.json is self-contained and stays available.
app = FastAPI(
    title="EMKA",
    description="Expeditionary Medical Knowledge Assistant — air-gapped reference service",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)


# --------------------------------------------------------------------------
# request/response models
# --------------------------------------------------------------------------


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    context: dict | None = None  # e.g. {"role": "role2"}


class FlagRequest(BaseModel):
    question: str
    reason: str = Field(min_length=3, max_length=2000)
    mode: str = ""
    chunk_ids: list[str] = []


class LabValue(BaseModel):
    lab_id: str
    value: float


class LabsRequest(BaseModel):
    """Lab interpretation input. Provide either free `text` to parse or an
    explicit `labs` list (or both). `context` carries non-PHI patient factors
    (sex, age, systolic_bp, bmi, diabetic, …) that sharpen bands and enable
    PREVENT. When `include_management` is set, Critical/Severe findings are
    linked to cited management guidance from the corpus.

    PHI: lab values and context are processed IN MEMORY ONLY and are NEVER
    written to the query log or any store (DESIGN.md §1, revised)."""

    text: str | None = Field(default=None, max_length=10000)
    labs: list[LabValue] = []
    context: dict | None = None
    include_management: bool = False


# ---------------------------------------------------------------------------
# local stores (never any patient data)
# ---------------------------------------------------------------------------

_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    ts TEXT NOT NULL, question TEXT NOT NULL, mode TEXT NOT NULL,
    source_ids TEXT NOT NULL, integrity INTEGER, confidence REAL,
    latency_s REAL, answer TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS flag_queue (
    ts TEXT NOT NULL, question TEXT NOT NULL, reason TEXT NOT NULL,
    mode TEXT NOT NULL, chunk_ids TEXT NOT NULL, resolved INTEGER DEFAULT 0
);
"""


def _log_conn(cfg: EmkaConfig) -> sqlite3.Connection:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(cfg.data_dir / "query-log.sqlite"))
    conn.executescript(_LOG_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# engine lifecycle — built lazily; tests inject via app.state.engine
# ---------------------------------------------------------------------------


def get_engine():
    if getattr(app.state, "engine", None) is None:
        from generate.answer import AnswerEngine

        app.state.engine = AnswerEngine(get_cfg())
    return app.state.engine


def get_cfg() -> EmkaConfig:
    if getattr(app.state, "cfg", None) is None:
        app.state.cfg = load_config()
    return app.state.cfg


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    cfg = get_cfg()
    index_built = (cfg.data_dir / "index" / "chunks.sqlite").exists()
    return {
        "status": "ok",
        "index_built": index_built,
        "no_phi_notice": NO_PHI_NOTICE,
    }


@app.post("/query")
def query(req: QueryRequest) -> dict:
    engine = get_engine()
    result = engine.answer(req.question, req.context)
    payload = result.to_dict()
    payload["no_phi_notice"] = NO_PHI_NOTICE

    conn = _log_conn(get_cfg())
    conn.execute(
        "INSERT INTO query_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(UTC).isoformat(timespec="seconds"),
            req.question,
            result.mode,
            json.dumps([s.chunk_id for s in result.sources]),
            int(bool(result.verification.get("integrity", False))),
            result.retrieval_confidence,
            result.latency_s,
            result.synthesis,
        ),
    )
    conn.commit()
    conn.close()
    return payload


def _most_severe_finding(results: list[dict]) -> dict | None:
    """Pick the single finding whose severity most warrants cited management —
    Critical over Severe, else None. Used to link labs to doctrine."""
    order = {"Critical": 2, "Severe": 1}
    ranked = [
        (order.get(str(r.get("severity", "")).split(" ")[0], 0), r)
        for r in results
        if "error" not in r
    ]
    ranked = [(rank, r) for rank, r in ranked if rank > 0]
    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


@app.post("/labs/interpret")
def labs_interpret(req: LabsRequest) -> dict:
    """Deterministic lab-value interpretation (labs/ package).

    Values are interpreted in memory and NEVER persisted — unlike /query,
    this route writes nothing to the query log. When include_management is set
    and the panel has a Critical/Severe finding, the corpus is queried for
    cited management guidance via the answer engine directly (which does not
    log), using a concept-level question that carries no numeric value."""
    from labs import evaluate_panel, load_rules, parse_text

    rules = load_rules()
    lab_inputs: list[tuple[str, float]] = [(lv.lab_id, lv.value) for lv in req.labs]
    if req.text:
        lab_inputs += [(p.lab_id, p.value) for p in parse_text(req.text, rules)]

    if not lab_inputs:
        raise HTTPException(status_code=422, detail="no recognizable labs in request")

    panel = evaluate_panel(lab_inputs, rules, req.context)

    management = None
    if req.include_management:
        finding = _most_severe_finding(panel["results"])
        if finding is not None:
            # concept-level question — display name + severity, never the value
            question = (
                f"management and workup of {finding['severity'].lower()} "
                f"{finding['display_name'].lower()}"
            )
            try:
                result = get_engine().answer(question, req.context)
                management = {"triggered_by": finding["lab_id"], "query": question}
                management.update(result.to_dict())
            except Exception as e:  # index may be absent; labs still work
                management = {"triggered_by": finding["lab_id"], "unavailable": str(e)}

    return {
        "findings": panel,
        "management": management,
        "no_phi_notice": NO_PHI_NOTICE,
    }


@app.post("/flag")
def flag(req: FlagRequest) -> dict:
    """UI 'flag this answer' -> maintainer queue (local, reviewed by the
    corpus custodian)."""
    conn = _log_conn(get_cfg())
    conn.execute(
        "INSERT INTO flag_queue (ts, question, reason, mode, chunk_ids) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now(UTC).isoformat(timespec="seconds"),
            req.question,
            req.reason,
            req.mode,
            json.dumps(req.chunk_ids),
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "flagged", "no_phi_notice": NO_PHI_NOTICE}


@app.get("/source/{doc_id}/page/{page}")
def source_page(doc_id: str, page: int) -> FileResponse:
    """Serve the source PDF for tap-to-open at a page. The whole file is
    returned; the client opens it at #page=<n>."""
    cfg = get_cfg()
    from ingest.queue import _index_corpus_files

    for shelf in ("authoritative", "unit"):
        index = _index_corpus_files(cfg.corpus_dir / shelf)
        path = index.get(doc_id.lower())
        if path is not None:
            return FileResponse(
                str(path),
                media_type="application/pdf",
                headers={"X-EMKA-Page": str(page), "X-EMKA-No-PHI": "reference-document"},
            )
    raise HTTPException(status_code=404, detail=f"no staged PDF for {doc_id}")


@app.post("/corpus/refresh")
def corpus_refresh() -> dict:
    """Maintainer action: re-run the manifest ingest queue, then reindex.
    Runs synchronously; on a full corpus this takes minutes."""
    import ingest.run as ingest_run
    from core.models import load_embedder
    from ingest.pipeline import load_all_chunks
    from retrieval.store import build_indexes

    cfg = get_cfg()
    ingest_rc = ingest_run.main([])
    chunks = load_all_chunks(cfg)
    if not chunks:
        raise HTTPException(status_code=409, detail="no chunks after ingest; check corpus/")
    build_indexes(chunks, cfg, load_embedder(cfg))
    # a fresh index invalidates the engine's open handles
    app.state.engine = None
    return {
        "status": "refreshed",
        "ingest_exit_code": ingest_rc,
        "n_chunks": len(chunks),
        "no_phi_notice": NO_PHI_NOTICE,
    }


# Ensure the file also works under `uvicorn api.main:app`
def main() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
