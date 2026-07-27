"""Tests for the labs/ package and the /labs/interpret endpoint.

The safety-critical assertion here is PHI: lab values must be interpreted in
memory and NEVER written to the query log (DESIGN.md §1, revised)."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from labs import evaluate, evaluate_panel, load_rules, parse_text


@pytest.fixture(scope="module")
def rules():
    return load_rules()


# --- engine -----------------------------------------------------------------


def test_severity_ladder(rules):
    assert evaluate("potassium", 7.5, rules)["severity"] == "Critical High"
    assert evaluate("potassium", 6.8, rules)["severity"] == "Severe High"
    assert evaluate("potassium", 2.5, rules)["severity"] == "Severe Low"


def test_unknown_lab_returns_error(rules):
    assert "error" in evaluate("unobtanium", 1.0, rules)


def test_follow_up_and_sources_present(rules):
    r = evaluate("potassium", 7.5, rules)
    assert r["follow_up"] and r["follow_up"]["ehr_plan"]
    assert r["sources"], "threshold provenance must be present"


def test_free_text_parse(rules):
    parsed = parse_text("K 6.8\nGlucose 320\nCr 2.1", rules)
    got = {(p.lab_id, p.value) for p in parsed}
    assert got == {("potassium", 6.8), ("glucose", 320.0), ("creatinine", 2.1)}


def test_panel_derives_egfr_and_ckd(rules):
    panel = evaluate_panel(
        [("creatinine", 2.1)], rules, {"age": 60, "sex": "male"}
    )
    d = panel["derived"]
    assert d["egfr"] is not None and d["egfr"] < 60
    assert d["ckd_g_stage"] in {"G3a", "G3b", "G4", "G5"}


# --- API: PHI must never be persisted ---------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EMKA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EMKA_CORPUS_DIR", str(tmp_path / "corpus"))
    from api.main import app

    app.state.cfg = None  # force reload against the temp dirs
    with TestClient(app) as c:
        yield c
    app.state.cfg = None


def test_labs_interpret_returns_findings(client):
    r = client.post("/labs/interpret", json={"text": "K 7.5\nGlucose 320"})
    assert r.status_code == 200
    body = r.json()
    ids = {f["lab_id"] for f in body["findings"]["results"]}
    assert {"potassium", "glucose"} <= ids
    assert "patient" in body["no_phi_notice"]


def test_labs_interpret_rejects_empty(client):
    assert client.post("/labs/interpret", json={"text": "no labs here"}).status_code == 422


def test_lab_values_never_hit_query_log(client):
    """The whole PHI contract: interpreting a lab writes nothing to the log."""
    from core.config import load_config

    client.post("/labs/interpret", json={"text": "K 7.5\nGlucose 320\nCr 2.1"})
    log = load_config().data_dir / "query-log.sqlite"
    if not log.exists():
        return  # nothing was written at all — the strongest possible pass
    conn = sqlite3.connect(log)
    try:
        rows = conn.execute("SELECT question, answer FROM query_log").fetchall()
    except sqlite3.OperationalError:
        return  # table never created
    finally:
        conn.close()
    blob = " ".join(str(c) for row in rows for c in row)
    for leak in ("7.5", "320", "potassium", "glucose"):
        assert leak not in blob, f"lab data {leak!r} leaked into the query log"
