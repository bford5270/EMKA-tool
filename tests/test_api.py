"""API tests with a stub-backed engine injected via app.state."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from capability.loadout import load_loadout
from core.config import load_config
from core.models import StubChatModel, StubEmbedder, StubReranker
from generate.answer import AnswerEngine
from retrieval.search import HybridRetriever
from retrieval.store import build_indexes
from tests.fixture_pdfs import build_sample_cpg
from tests.test_answer import CHUNKS, TEMPLATES


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    base = tmp_path_factory.mktemp("api")
    import os

    os.environ["EMKA_DATA_DIR"] = str(base / "data")
    os.environ["EMKA_CORPUS_DIR"] = str(base / "corpus")
    cap_dir = base / "corpus" / "unit" / "capability"
    cap_dir.mkdir(parents=True)
    for f in TEMPLATES.glob("*.yaml"):
        shutil.copy(f, cap_dir / f.name)
    (base / "corpus" / "authoritative").mkdir(parents=True)
    build_sample_cpg(base / "corpus" / "authoritative" / "CPG-03.pdf")

    try:
        cfg = load_config()
        embedder, reranker = StubEmbedder(), StubReranker()
        build_indexes(CHUNKS, cfg, embedder)
        from datetime import date

        app.state.cfg = cfg
        app.state.engine = AnswerEngine(
            cfg,
            retriever=HybridRetriever(cfg, embedder=embedder, reranker=reranker),
            chat=StubChatModel(),
            loadout=load_loadout(cfg, today=date(2026, 7, 11)),
        )
        with TestClient(app) as c:
            yield c, cfg
    finally:
        app.state.engine = None
        app.state.cfg = None
        del os.environ["EMKA_DATA_DIR"]
        del os.environ["EMKA_CORPUS_DIR"]


def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["index_built"]
    assert "patient" in body["no_phi_notice"]


def test_query_returns_structured_result_and_logs(client):
    c, cfg = client
    r = c.post(
        "/query",
        json={
            "question": "blood product ratio for massive transfusion",
            "context": {"role": "role2"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "synthesized"
    assert body["sources"] and body["citations"]
    assert body["verification"]["integrity"] is True
    assert "patient" in body["no_phi_notice"]

    conn = sqlite3.connect(cfg.data_dir / "query-log.sqlite")
    rows = conn.execute("SELECT question, mode, source_ids FROM query_log").fetchall()
    conn.close()
    assert rows and "massive transfusion" in rows[-1][0]
    assert "CPG-03:00000" in rows[-1][2]


def test_query_validates_input(client):
    c, _ = client
    assert c.post("/query", json={"question": "hi"}).status_code == 422


def test_source_pdf_served(client):
    c, _ = client
    r = c.get("/source/CPG-03/page/2")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-emka-page"] == "2"
    assert r.content.startswith(b"%PDF")


def test_source_pdf_missing_404(client):
    c, _ = client
    assert c.get("/source/NOPE-99/page/1").status_code == 404


def test_flag_answer_lands_in_maintainer_queue(client):
    c, cfg = client
    r = c.post(
        "/flag",
        json={
            "question": "massive transfusion ratio",
            "reason": "citation points at the wrong paragraph",
            "mode": "synthesized",
            "chunk_ids": ["CPG-03:00000"],
        },
    )
    assert r.status_code == 200 and r.json()["status"] == "flagged"
    conn = sqlite3.connect(cfg.data_dir / "query-log.sqlite")
    rows = conn.execute("SELECT question, reason, resolved FROM flag_queue").fetchall()
    conn.close()
    assert rows and rows[-1][1].startswith("citation points") and rows[-1][2] == 0


def test_corpus_refresh_reingests_and_reindexes(client, monkeypatch):
    c, cfg = client
    monkeypatch.setenv("EMKA_ALLOW_STUB_MODELS", "1")
    r = c.post("/corpus/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "refreshed" and body["n_chunks"] > 0
    # index now reflects the staged corpus (CPG-03 fixture), engine reset
    assert app.state.engine is None
    assert (Path(cfg.data_dir) / "chunks" / "CPG-03.jsonl").exists()
