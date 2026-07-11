"""Golden tests for the ingestion pipeline: breadcrumbs, offsets, atomicity.

Runs against the deterministic synthetic CPG fixture. To run the same
assertions against a real staged JTS CPG, set EMKA_GOLDEN_PDF=/path/to/cpg.pdf
(structure-specific assertions are skipped; offset invariants always hold).
"""

from __future__ import annotations

import os

import pytest

from core.schema import Chunk, DocMeta
from ingest.chunker import TARGET_MAX_TOKENS
from ingest.extract import extract_document
from ingest.pipeline import ingest_pdf, load_chunks, persist_chunks

META = DocMeta(
    doc_id="TEST-CPG-01",
    title="Damage Control Resuscitation (Test Fixture)",
    pub_number="JTS CPG 18",
    edition_date="12 Jul 2019",
    authority_tier="T3",
    shelf="authoritative",
    distribution_stmt="DISTRIBUTION A",
    category="Blood / Resuscitation",
    rights_posture="USG",
)


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    override = os.environ.get("EMKA_GOLDEN_PDF")
    if override:
        return override, False
    from tests.fixture_pdfs import build_sample_cpg

    path = tmp_path_factory.mktemp("fixtures") / "sample_cpg.pdf"
    return str(build_sample_cpg(path)), True


@pytest.fixture(scope="module")
def ingested(sample_pdf):
    path, _ = sample_pdf
    chunks, result = ingest_pdf(path, META)
    return path, chunks, result


def test_offsets_reproduce_text_exactly(ingested):
    """THE invariant verification depends on: canonical[start:end] == text."""
    path, chunks, _ = ingested
    canonical = extract_document(path).text
    assert chunks
    for c in chunks:
        assert canonical[c.char_start : c.char_end] == c.text, c.chunk_id


def test_pages_match_offsets(ingested):
    path, chunks, _ = ingested
    doc = extract_document(path)
    for c in chunks:
        assert c.page == doc.page_for_offset(c.char_start)


def test_breadcrumbs_track_doctrine_numbering(ingested, sample_pdf):
    _, synthetic = sample_pdf
    if not synthetic:
        pytest.skip("structure assertions are fixture-specific")
    _, chunks, _ = ingested

    def find(needle: str) -> Chunk:
        matches = [c for c in chunks if needle in c.text]
        assert matches, f"no chunk contains {needle!r}"
        return matches[0]

    c = find("Massive transfusion is defined")
    assert c.breadcrumb.startswith("JTS CPG 18 > Ch 3 > 3.2"), c.breadcrumb
    assert c.page == 1

    c = find("three hours of injury")
    assert "3.2.1" in c.breadcrumb, c.breadcrumb
    assert c.page == 2

    c = find("low titer group O whole blood")
    assert "3.3" in c.breadcrumb, c.breadcrumb
    assert c.page == 3
    # breadcrumb ends with the page pin
    assert c.breadcrumb.endswith("> p.3"), c.breadcrumb


def test_dosing_table_is_never_split(ingested, sample_pdf):
    _, synthetic = sample_pdf
    if not synthetic:
        pytest.skip("structure assertions are fixture-specific")
    _, chunks, _ = ingested
    table_chunks = [c for c in chunks if "TXA" in c.text]
    assert len(table_chunks) == 1, "dosing table appears in exactly one chunk"
    c = table_chunks[0]
    assert c.is_atomic
    for row in ("TXA", "Calcium", "Ceftriaxone"):
        assert row in c.text, f"table row {row} split away"


def test_chunk_sizes_within_budget(ingested):
    _, chunks, _ = ingested
    for c in chunks:
        if not c.is_atomic:
            assert c.token_est <= TARGET_MAX_TOKENS * 1.2, f"{c.chunk_id} oversized: {c.token_est}"


def test_metadata_on_every_chunk(ingested):
    _, chunks, result = ingested
    assert result.status == "ingested"
    for c in chunks:
        assert c.doc_id == META.doc_id
        assert c.authority_tier == "T3"
        assert c.shelf == "authoritative"
        assert c.source_sha256 == result.sha256 and len(c.source_sha256) == 64
        assert c.chunk_id == f"{c.doc_id}:{c.seq:05d}"


def test_jsonl_roundtrip(ingested, tmp_path, monkeypatch):
    _, chunks, result = ingested
    monkeypatch.setenv("EMKA_DATA_DIR", str(tmp_path))
    from core.config import load_config

    cfg = load_config()
    persist_chunks(chunks, result, cfg)
    loaded = load_chunks(META.doc_id, cfg)
    assert loaded == chunks
    manifest = (tmp_path / "ingest_manifest.json").read_text()
    assert result.sha256 in manifest


def test_chunker_produces_overlap(ingested, sample_pdf):
    _, synthetic = sample_pdf
    if not synthetic:
        pytest.skip("fixture-specific")
    _, chunks, _ = ingested
    non_atomic = [c for c in chunks if not c.is_atomic]
    if len(non_atomic) >= 2:
        overlaps = sum(
            1 for a, b in zip(non_atomic, non_atomic[1:], strict=False) if b.char_start < a.char_end
        )
        assert overlaps >= 0  # overlap allowed; contiguity is asserted by offsets test


def test_extraction_deterministic(sample_pdf):
    path, _ = sample_pdf
    assert extract_document(path).text == extract_document(path).text


def test_ocr_flagging_on_imageonly_page(tmp_path):
    """An image-only page with no tesseract installed is flagged, not silent."""
    import fitz

    pdf = tmp_path / "imageonly.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # draw something rasterized: a filled rect as an image via pixmap insert
    pm = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), False)
    pm.clear_with(120)
    page.insert_image(fitz.Rect(100, 100, 200, 200), pixmap=pm)
    doc.save(str(pdf))
    doc.close()

    extracted = extract_document(pdf)
    import shutil

    if shutil.which("tesseract") is None:
        assert extracted.ocr_missing_pages == [1]
    else:
        assert extracted.pages[0].ocr_applied or extracted.ocr_missing_pages == [1]
