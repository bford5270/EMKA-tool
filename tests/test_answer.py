"""Orchestrator tests: retrieve -> synthesize -> verify -> assemble,
including the fail-safe (regenerate once, then raw passages) and
capability matching. Stub backends throughout — deterministic."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from capability.loadout import load_loadout
from core.config import load_config
from core.models import StubChatModel, StubEmbedder, StubReranker
from generate.answer import AnswerEngine
from retrieval.search import HybridRetriever
from retrieval.store import build_indexes
from tests.test_retrieval import make_chunk

TEMPLATES = Path(__file__).resolve().parent.parent / "capability" / "templates"

CHUNKS = [
    make_chunk(
        "CPG-31",
        0,
        "For intra-abdominal infection, ertapenem 1 g IV q24h is the preferred "
        "empiric agent. If ertapenem is unavailable, moxifloxacin 400 mg IV q24h "
        "is the stated alternative.",
        "CPG-31 > Ch 2 > 2.4 > p.5",
    ),
    make_chunk(
        "CPG-03",
        0,
        "Massive transfusion requires balanced resuscitation with plasma and red "
        "blood cells in a one to one ratio. Crystalloid should be minimized.",
        "CPG-03 > Ch 3 > 3.2 > p.1",
    ),
    make_chunk(
        "UNT-01",
        0,
        "Unit SOP: all casualties receiving blood products get a second IV line "
        "and hypothermia prevention wrap before movement.",
        "UNT-01 > 4-2 > p.12",
        shelf="unit",
        authority_tier="T1",
    ),
]


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    base = tmp_path_factory.mktemp("answer")
    os.environ["EMKA_DATA_DIR"] = str(base / "data")
    os.environ["EMKA_CORPUS_DIR"] = str(base / "corpus")
    cap_dir = base / "corpus" / "unit" / "capability"
    cap_dir.mkdir(parents=True)
    for f in TEMPLATES.glob("*.yaml"):
        shutil.copy(f, cap_dir / f.name)
    try:
        cfg = load_config()
        embedder, reranker = StubEmbedder(), StubReranker()
        build_indexes(CHUNKS, cfg, embedder)
        retriever = HybridRetriever(cfg, embedder=embedder, reranker=reranker)
        from datetime import date

        loadout = load_loadout(cfg, today=date(2026, 7, 11))
        yield AnswerEngine(cfg, retriever=retriever, chat=StubChatModel(), loadout=loadout)
    finally:
        del os.environ["EMKA_DATA_DIR"]
        del os.environ["EMKA_CORPUS_DIR"]


def test_synthesized_answer_is_verified_and_structured(engine):
    result = engine.answer("blood product ratio for massive transfusion resuscitation")
    assert result.mode == "synthesized" and not result.abstained
    assert result.verification["integrity"]
    assert result.citations and all(c["passed"] for c in result.citations)
    assert '<quote src="' in result.synthesis
    assert result.sources, "sources must always be returned (sources are primary)"
    assert result.latency_s > 0
    assert "patient data" in result.no_phi_notice


def test_capability_matching_surfaces_unavailable_first_line(engine):
    """First-line ertapenem is not stocked at role2 -> availability finding
    False; the source's own alternative (moxifloxacin) is in the passages."""
    result = engine.answer(
        "empiric antibiotic for intra-abdominal infection", context={"role": "role2"}
    )
    assert result.mode == "synthesized"
    notes = {n["matched_name"]: n for n in result.capability_notes}
    assert notes["ertapenem"]["available"] is False
    assert notes["moxifloxacin"]["available"] is True
    # the alternative is present in the returned sources, quoted from doctrine
    assert any("moxifloxacin" in s.text for s in result.sources)
    assert "Availability note" in result.synthesis


def test_unit_shelf_sources_watermarked(engine):
    result = engine.answer("second IV line and hypothermia prevention wrap SOP")
    unit_sources = [s for s in result.sources if s.shelf == "unit"]
    assert unit_sources and all(s.unit_watermark for s in unit_sources)


def test_abstention_flows_through(engine):
    result = engine.answer("orbital mechanics of geosynchronous satellites")
    assert result.mode == "abstained" and result.abstained
    assert "does not adequately support" in result.synthesis
    assert result.abstain_reason


def test_failsafe_returns_raw_passages_after_two_failures(engine):
    class FabricatingChat:
        backend = "stub"

        def complete(self, messages, max_tokens=1024, temperature=0.1):
            # always emits a quote that does not exist in any chunk
            return '<quote src="CPG-03:00000">invented dosing guidance</quote>'

    bad = AnswerEngine(
        engine.cfg,
        retriever=engine.retriever,
        chat=FabricatingChat(),
        loadout=engine.loadout,
    )
    result = bad.answer("massive transfusion ratio")
    assert result.mode == "raw_passages"
    assert result.synthesis == ""
    assert not result.verification["integrity"]
    assert result.sources, "raw passages must still be delivered"


def test_regeneration_recovers_when_second_attempt_verifies(engine):
    class FlakyChat:
        backend = "stub"

        def __init__(self):
            self.calls = 0
            self._good = StubChatModel()

        def complete(self, messages, max_tokens=1024, temperature=0.1):
            self.calls += 1
            if self.calls == 1:
                return '<quote src="CPG-03:00000">altered quote text</quote>'
            return self._good.complete(messages, max_tokens, temperature)

    flaky = FlakyChat()
    eng = AnswerEngine(engine.cfg, retriever=engine.retriever, chat=flaky, loadout=engine.loadout)
    result = eng.answer("massive transfusion ratio")
    assert flaky.calls == 2
    assert result.mode == "synthesized" and result.verification["integrity"]


def test_result_serializes(engine):
    result = engine.answer("massive transfusion ratio")
    d = result.to_dict()
    assert d["mode"] == "synthesized"
    assert isinstance(d["sources"], list) and isinstance(d["sources"][0], dict)
