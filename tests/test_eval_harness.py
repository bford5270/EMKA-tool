"""Eval harness tests: metric mechanics, gating, per-case context loadouts.
Runs a stub-backed engine over a corpus aligned to a few real seed cases."""

from __future__ import annotations

import json
import os

import pytest

from core.config import load_config
from core.models import StubChatModel, StubEmbedder, StubReranker
from eval.run import (
    aggregate,
    gate,
    grade_element_keyword,
    load_cases,
    loadout_from_context,
    run,
    score_case,
)
from generate.answer import AnswerEngine
from retrieval.search import HybridRetriever
from retrieval.store import build_indexes
from tests.test_retrieval import make_chunk

# corpus aligned with EMKA-EVAL-001 (TXA) and the abstain cases
CHUNKS = [
    make_chunk(
        "CPG-01",
        0,
        "Tranexamic acid TXA is indicated for casualties with significant hemorrhage "
        "or anticipated massive transfusion. Administer as early as possible after "
        "injury and within the recommended time window as an infusion, not rapid IV push.",
        "CPG-01 > TXA > p.4",
    ),
    make_chunk(
        "CPG-03",
        0,
        "Damage control resuscitation pairs early hemorrhage control with balanced "
        "blood product transfusion and calcium chloride as the stated alternative "
        "for calcium management during massive transfusion when calcium gluconate "
        "is unavailable.",
        "CPG-03 > Ch 3 > 3.4 > p.7",
    ),
]


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    base = tmp_path_factory.mktemp("eval")
    os.environ["EMKA_DATA_DIR"] = str(base / "data")
    os.environ["EMKA_CORPUS_DIR"] = str(base / "corpus")  # no capability files staged
    try:
        cfg = load_config()
        embedder, reranker = StubEmbedder(), StubReranker()
        build_indexes(CHUNKS, cfg, embedder)
        yield AnswerEngine(
            cfg,
            retriever=HybridRetriever(cfg, embedder=embedder, reranker=reranker),
            chat=StubChatModel(),
            loadout=None,
        )
    finally:
        del os.environ["EMKA_DATA_DIR"]
        del os.environ["EMKA_CORPUS_DIR"]


def _case(case_id: str) -> dict:
    _, cases = load_cases()
    return next(c for c in cases if c["id"] == case_id)


def test_seed_cases_load_and_are_complete():
    metadata, cases = load_cases()
    assert len(cases) == metadata["seed_case_count"] == 30
    assert set(metadata["thresholds"]) == {
        "retrieval_recall_at_10",
        "citation_accuracy",
        "verbatim_quote_integrity",
        "grounded_answer_rate",
        "honest_abstention_rate",
        "latency_seconds_max",
    }
    for c in cases:
        assert c["expected_behavior"] in {"answer", "abstain"}
        assert c["exercises"]


def test_answer_case_scoring(engine):
    score = score_case(_case("EMKA-EVAL-001"), engine, "keyword")
    assert score.recall_at_10 is True  # CPG-01 chunk retrieved
    assert score.quote_integrity_ok is True
    assert score.citation_ok is True  # stub quotes the top (expected) source
    assert score.latency_s > 0
    assert score.honest_abstention is None  # not an abstain case


def test_abstain_case_scoring(engine):
    score = score_case(_case("EMKA-EVAL-025"), engine, "keyword")  # generators
    assert score.expected_behavior == "abstain"
    assert score.honest_abstention is True
    assert score.recall_at_10 is None  # no expected sources


def test_resource_matching_case_uses_context_loadout(engine):
    case = _case("EMKA-EVAL-029")  # calcium gluconate absent / chloride present
    lo = loadout_from_context(case["context"])
    findings = {f.matched_name: f for f in lo.match("calcium gluconate or calcium chloride")}
    assert findings["calcium gluconate"].available is False
    assert findings["calcium chloride"].available is True

    score = score_case(case, engine, "keyword")
    assert score.recall_at_10 is True  # CPG-03 chunk present


def test_keyword_grader():
    assert grade_element_keyword(
        "administered as an infusion, not a rapid IV push",
        "TXA should be administered as an infusion, not rapid IV push, early.",
    )
    assert not grade_element_keyword(
        "walking blood bank donor screening requirements",
        "completely unrelated evidence text about water purification",
    )


def test_aggregate_and_gate_logic():
    from eval.run import CaseScore

    scores = [
        CaseScore(
            "A",
            "answer",
            "synthesized",
            recall_at_10=True,
            citation_ok=True,
            quote_integrity_ok=True,
            grounded=True,
            latency_s=1.0,
        ),
        CaseScore("B", "abstain", "abstained", honest_abstention=True, latency_s=2.0),
        CaseScore(
            "C",
            "answer",
            "synthesized",
            recall_at_10=False,
            citation_ok=False,
            quote_integrity_ok=True,
            grounded=False,
            latency_s=40.0,
        ),
    ]
    m = aggregate(scores)
    assert m["retrieval_recall_at_10"] == 0.5
    assert m["honest_abstention_rate"] == 1.0
    assert m["latency_seconds_max"] == 40.0
    breaches = gate(
        m,
        {"retrieval_recall_at_10": 0.95, "latency_seconds_max": 30, "honest_abstention_rate": 0.95},
    )
    assert len(breaches) == 2  # recall low + latency high


def test_full_run_emits_report_and_gates(engine, capsys):
    cfg = engine.cfg
    rc = run(["--only", "EMKA-EVAL-001,EMKA-EVAL-025", "--report-only"], engine=engine)
    assert rc == 0
    out = capsys.readouterr().out
    assert "STUB MODELS ACTIVE" in out
    report = json.loads((cfg.data_dir / "eval_report.json").read_text())
    assert report["metadata"]["n_cases"] == 2
    assert report["metadata"]["stub_models"] is True
    assert {c["case_id"] for c in report["cases"]} == {"EMKA-EVAL-001", "EMKA-EVAL-025"}

    # even without --report-only, a STUB run must never gate (DESIGN.md §10):
    # stub numbers exercise mechanics only, so exit is 0 regardless of breaches.
    rc = run(["--only", "EMKA-EVAL-001,EMKA-EVAL-026"], engine=engine)
    assert rc == 0
    report = json.loads((cfg.data_dir / "eval_report.json").read_text())
    assert report["metadata"]["gating_enabled"] is False


def test_stub_run_does_not_gate_despite_breaches(engine):
    """A guaranteed-breach case (out-of-corpus 'answer' expectation) still
    exits 0 under stub models, and the report records gating as disabled."""
    rc = run(["--only", "EMKA-EVAL-001"], engine=engine)
    assert rc == 0
    report = json.loads((engine.cfg.data_dir / "eval_report.json").read_text())
    assert report["metadata"]["stub_models"] is True
    assert report["metadata"]["gating_enabled"] is False


def test_care_role_mapping():
    from eval.run import care_role_for

    assert care_role_for({"role": "IDC"}) == "role1"
    assert care_role_for({"role": "Role2"}) == "role2"
    assert care_role_for({"role": "DNBI"}) == "role1"
    assert care_role_for({"role": "Planner"}) == "role2"
    # an explicit context.role overrides the top-level role
    assert care_role_for({"role": "IDC", "context": {"role": "role3"}}) == "role3"
    # unknown roles fall back to role2
    assert care_role_for({"role": "spaceforce"}) == "role2"
