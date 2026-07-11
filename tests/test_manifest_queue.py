"""Manifest loader + ingest queue tests, run against the REAL manifest
(docs/EMKA_Corpus_Manifest.xlsx) so parsing tracks the actual artifact."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.manifest import load_manifest
from ingest.queue import build_queue, row_to_docmeta

MANIFEST = Path(__file__).resolve().parent.parent / "docs" / "EMKA_Corpus_Manifest.xlsx"


@pytest.fixture(scope="module")
def rows():
    return load_manifest(MANIFEST)


def test_manifest_loads_all_sheets(rows):
    assert len(rows) > 150, "expected the ~227-item corpus"
    sheets = {r.sheet for r in rows}
    assert "JTS CPGs" in sheets and "Capability & Formulary" in sheets


def test_known_rows_normalized(rows):
    by_id = {r.ref_id: r for r in rows}
    cpg1 = by_id["CPG-01"]
    assert cpg1.tier == "T3"
    assert cpg1.shelf == "authoritative"
    assert cpg1.phase == "0" and cpg1.is_phase_core
    assert not cpg1.rights_gated  # USG

    # Unit-shelf item
    unt1 = by_id["UNT-01"]
    assert unt1.shelf == "unit" and unt1.tier == "T1"

    # VERIFY rights must gate
    or1 = by_id["OR-01"]
    assert or1.rights_gated


def test_ref_ids_unique(rows):
    ids = [r.ref_id for r in rows]
    assert len(ids) == len(set(ids)), "duplicate Ref IDs in manifest"


def test_queue_filters_and_reports(rows, tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / "authoritative").mkdir(parents=True)
    (corpus / "unit").mkdir()

    # stage one matching PDF under each naming convention + one stray
    from tests.fixture_pdfs import build_sample_cpg

    build_sample_cpg(corpus / "authoritative" / "CPG-03.pdf")
    build_sample_cpg(corpus / "authoritative" / "CPG-02__Prolonged_Casualty_Care.pdf")
    build_sample_cpg(corpus / "authoritative" / "NOT-A-REF.pdf")

    report = build_queue(rows, corpus)

    matched_ids = {r.ref_id for r, _ in report.matched}
    assert matched_ids == {"CPG-03", "CPG-02"}

    # rights-gated Phase-0 authoritative rows are listed and skipped
    gated_ids = {r.ref_id for r in report.rights_gated}
    assert "OR-01" in gated_ids
    assert all(r.ref_id not in matched_ids for r in report.rights_gated)

    # everything else in phase 0 / authoritative without a file is missing
    missing_ids = {r.ref_id for r in report.missing_file}
    assert "CPG-01" in missing_ids
    # non-core phases and unit shelf are out of scope for the first build
    out_ids = {r.ref_id for r in report.out_of_scope}
    assert "UNT-01" in out_ids and "PC-03" in out_ids

    # stray file is surfaced, not silently ignored
    assert [p.name for p in report.unmatched_files] == ["NOT-A-REF.pdf"]

    # summary mentions the gated rows by id
    assert "OR-01" in report.summary()


def test_row_to_docmeta(rows):
    row = next(r for r in rows if r.ref_id == "CPG-03")
    meta = row_to_docmeta(row)
    assert meta.doc_id == meta.pub_number == "CPG-03"
    assert meta.authority_tier == "T3"
    assert meta.shelf == "authoritative"
    assert meta.rights_posture == "USG"


def test_ingest_log_roundtrip(tmp_path):
    from ingest.ingest_log import IngestLog

    log = IngestLog(tmp_path / "ingest-log.sqlite")
    log.record("CPG-03", "ingested", sha256="ab" * 32, n_chunks=12, n_pages=3)
    log.record("CPG-03", "failed", error="boom")
    latest = log.latest("CPG-03")
    assert latest["status"] == "failed" and latest["error"] == "boom"
    assert log.latest("NOPE") is None
    log.close()


def test_end_to_end_ingest_run(rows, tmp_path, monkeypatch, capsys):
    """make ingest against a corpus dir with one staged Phase-0 PDF."""
    corpus = tmp_path / "corpus"
    (corpus / "authoritative").mkdir(parents=True)
    from tests.fixture_pdfs import build_sample_cpg

    build_sample_cpg(corpus / "authoritative" / "CPG-03.pdf")
    monkeypatch.setenv("EMKA_CORPUS_DIR", str(corpus))
    monkeypatch.setenv("EMKA_DATA_DIR", str(tmp_path / "data"))

    from ingest.run import main

    assert main([]) == 0
    out = capsys.readouterr().out
    assert "+ CPG-03" in out
    assert (tmp_path / "data" / "chunks" / "CPG-03.jsonl").exists()
    assert (tmp_path / "data" / "ingest-log.sqlite").exists()

    # second run: unchanged file is skipped, not re-ingested
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "unchanged" in out
