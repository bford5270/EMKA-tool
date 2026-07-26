"""Hybrid retrieval tests (stub backends: deterministic, no weights needed).

Covers the playbook's two required cases — an exact-term doctrine query that
the keyword path should win, and a semantic clinical query — plus fusion,
citation metadata passthrough, and the abstention gate.
"""

from __future__ import annotations

import pytest

from core.config import load_config
from core.models import StubEmbedder, StubReranker
from core.schema import Chunk
from retrieval.search import HybridRetriever
from retrieval.store import ChunkStore, build_indexes


def make_chunk(doc_id: str, seq: int, text: str, breadcrumb: str, **over) -> Chunk:
    meta = dict(
        title=f"Test Doc {doc_id}",
        pub_number=doc_id,
        edition_date="01 Jan 2026",
        authority_tier="T3",
        shelf="authoritative",
        distribution_stmt="",
        category="Test",
        rights_posture="USG",
        source_sha256="0" * 64,
        page=1,
        char_start=0,
        char_end=len(text),
        is_atomic=False,
        token_est=len(text.split()),
    )
    meta.update(over)
    return Chunk(
        chunk_id=f"{doc_id}:{seq:05d}",
        doc_id=doc_id,
        seq=seq,
        breadcrumb=breadcrumb,
        text=text,
        **meta,
    )


CHUNKS = [
    make_chunk(
        "CPG-03",
        0,
        "Massive transfusion protocols require balanced resuscitation with plasma "
        "and red blood cells in a one to one ratio, adding platelets when available.",
        "CPG-03 > Ch 3 > 3.2 > p.1",
    ),
    make_chunk(
        "CPG-03",
        1,
        "Drug Dose Route Frequency\nTXA 2 g IV single bolus\nCeftriaxone 1 g IV q24h "
        "if indicated\nCalcium 1 g IV after first unit",
        "CPG-03 > Ch 3 > 3.2.1 > p.2",
        is_atomic=True,
        page=2,
    ),
    make_chunk(
        "CPG-05",
        0,
        "Cold stored low titer group O whole blood is the preferred resuscitation "
        "product for hemorrhagic shock in the deployed environment.",
        "CPG-05 > Ch 1 > 1.2 > p.3",
        edition_date="15 May 2018",
    ),
    make_chunk(
        "NTTP-01",
        0,
        "Water purification aboard expeditionary platforms uses reverse osmosis "
        "units; chlorination follows preventive medicine guidance.",
        "NTTP-01 > Ch 9 > 9.1 > p.9",
        authority_tier="T4",
    ),
]


@pytest.fixture(scope="module")
def retriever(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    import os

    os.environ["EMKA_DATA_DIR"] = str(data_dir)
    try:
        cfg = load_config()
        embedder, reranker = StubEmbedder(), StubReranker()
        build_indexes(CHUNKS, cfg, embedder)
        yield HybridRetriever(cfg, embedder=embedder, reranker=reranker)
    finally:
        del os.environ["EMKA_DATA_DIR"]


def test_exact_term_doctrine_query_favors_keyword(retriever):
    """Rare exact tokens (drug name + frequency) should surface via BM25."""
    result = retriever.search("ceftriaxone q24h dosing")
    assert not result.abstained
    top = result.chunks[0]
    assert "Ceftriaxone" in top.chunk.text
    assert top.keyword_rank is not None and top.keyword_rank <= 3
    assert top.chunk.is_atomic  # the dosing table came through intact


def test_semantic_clinical_query(retriever):
    result = retriever.search("what blood product ratios for massive transfusion resuscitation")
    assert not result.abstained
    texts = [rc.chunk.text for rc in result.chunks[:2]]
    assert any("one to one ratio" in t for t in texts)


def test_results_carry_citation_and_precedence_metadata(retriever):
    result = retriever.search("whole blood resuscitation for hemorrhagic shock")
    assert result.chunks
    for rc in result.chunks:
        assert rc.chunk.authority_tier in {"T1", "T2", "T3", "T4", "T5"}
        assert rc.chunk.edition_date
        assert rc.chunk.breadcrumb and rc.chunk.pub_number
    assert 0.0 <= result.retrieval_confidence <= 1.0


def test_fusion_merges_both_paths(retriever):
    result = retriever.search("whole blood transfusion")
    found_by = {(rc.dense_rank is not None, rc.keyword_rank is not None) for rc in result.chunks}
    assert found_by, "no results"
    # every result must be locatable by at least one path
    assert all(d or k for d, k in found_by)


def test_abstention_on_out_of_corpus_query(retriever):
    result = retriever.search("submarine nuclear reactor coolant chemistry procedures")
    assert result.abstained
    assert result.abstain_reason.startswith("insufficient corpus support")
    assert result.retrieval_confidence < retriever.cfg.abstention_threshold


def test_top_k_respected(retriever):
    result = retriever.search("blood", top_k=2)
    assert len(result.chunks) <= 2


def test_store_hydration_roundtrip(retriever):
    store = ChunkStore(retriever.cfg)
    assert store.count() == len(CHUNKS)
    c = store.get("CPG-03:00001")
    assert c == CHUNKS[1]
    with pytest.raises(KeyError):
        store.get("NOPE:00000")
    store.close()
