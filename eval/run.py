"""``make eval`` — gold-standard question harness. Gates every change.

Runs every case in eval/seed_cases.yaml through the full answer pipeline and
scores (metric definitions in DESIGN.md §10 and eval/README.md):

    retrieval_recall_at_10    expected_source_ref doc appears in top-10 retrieval
    citation_accuracy         displayed citations point into expected sources
    verbatim_quote_integrity  displayed quotes passed the verifier (enforced)
    grounded_answer_rate      answer_must_include rubric elements present+supported
    honest_abstention_rate    abstain-cases actually abstain (no improvisation)
    latency_seconds_max       max query-to-answer time

Exit code is non-zero when any metric falls below the thresholds in the YAML
(--report-only disables gating). Rubric grading is keyword-based by default
(deterministic; an approximation, flagged in the report); on a provisioned
device --grader=model uses the chat model against the rubric.

Cases with a ``context`` block (resource_matching / capability_limit) run
against an ephemeral loadout built from that context, so availability logic
is exercised without touching the staged unit files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import yaml

from capability.loadout import Dataset, FormularyItem, Loadout
from core.config import load_config
from generate.answer import AnswerEngine, AnswerResult

CASES_PATH = Path(__file__).resolve().parent / "seed_cases.yaml"

_STOPWORDS = frozenset(
    "the a an and or of for with to in on at by is are be as not no does do "
    "its it this that there their any all optionally states rather than".split()
)


@dataclass
class CaseScore:
    case_id: str
    expected_behavior: str
    mode: str
    recall_at_10: bool | None = None  # None = not applicable
    citation_ok: bool | None = None
    quote_integrity_ok: bool | None = None
    grounded: bool | None = None
    honest_abstention: bool | None = None
    latency_s: float = 0.0
    element_hits: list[bool] = field(default_factory=list)
    notes: str = ""


def load_cases(path: Path = CASES_PATH) -> tuple[dict, list[dict]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["metadata"], data["cases"]


# ---------------------------------------------------------------------------
# per-case context -> ephemeral loadout
# ---------------------------------------------------------------------------


def loadout_from_context(context: dict) -> Loadout | None:
    formulary: list[FormularyItem] = []
    all_roles = {"role1": True, "role2": True, "role3": True}
    no_roles = {"role1": False, "role2": False, "role3": False}
    for name in context.get("formulary_present", []):
        formulary.append(FormularyItem(name=str(name), synonyms=(), stocked=dict(all_roles)))
    for name in context.get("formulary_absent", []):
        formulary.append(FormularyItem(name=str(name), synonyms=(), stocked=dict(no_roles)))
    if not formulary:
        return None
    ds = Dataset(kind="formulary", as_of=date.today(), source="eval-case context", stale=False)
    return Loadout(formulary, [], {}, {}, [], {"formulary": ds})


# ---------------------------------------------------------------------------
# rubric grading
# ---------------------------------------------------------------------------


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3 and w not in _STOPWORDS}


def grade_element_keyword(element: str, evidence: str) -> bool:
    """Deterministic approximation: an element counts as present when at
    least half of its content words occur in the answer+sources evidence."""
    words = _content_words(element)
    if not words:
        return True
    evidence_words = _content_words(evidence)
    return len(words & evidence_words) / len(words) >= 0.5


def grade_case_keyword(case: dict, result: AnswerResult) -> tuple[bool, list[bool]]:
    evidence = "\n".join(
        [result.synthesis]
        + [s.text for s in result.sources]
        + [json.dumps(n) for n in result.capability_notes]
    )
    hits = [grade_element_keyword(el, evidence) for el in case.get("answer_must_include", [])]
    # keyword mode: >=60% of rubric elements present counts as grounded
    return (sum(hits) / len(hits) >= 0.6 if hits else True), hits


def grade_case_model(case: dict, result: AnswerResult, chat) -> tuple[bool, list[bool]]:
    """Rubric grading by the local chat model (device use)."""
    hits: list[bool] = []
    for el in case.get("answer_must_include", []):
        prompt = (
            "Grade strictly. RUBRIC ELEMENT:\n"
            f"{el}\n\nANSWER AND SOURCES:\n{result.synthesis}\n\n"
            + "\n".join(s.text for s in result.sources)
            + "\n\nIs the rubric element present AND supported by the sources? "
            "Reply with exactly YES or NO."
        )
        reply = chat.complete([{"role": "user", "content": prompt}], max_tokens=4)
        hits.append(reply.strip().upper().startswith("YES"))
    return all(hits) if hits else True, hits


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def score_case(case: dict, engine: AnswerEngine, grader: str) -> CaseScore:
    context = dict(case.get("context") or {})
    role = context.get("role", "role2")
    case_loadout = loadout_from_context(context)
    if case_loadout is not None:
        engine = AnswerEngine(
            engine.cfg,
            retriever=engine.retriever,
            chat=engine.chat,
            loadout=case_loadout,
            canonical_lookup=engine.canonical_lookup,
        )

    t0 = time.perf_counter()
    result = engine.answer(case["question"], {"role": role})
    latency = time.perf_counter() - t0

    expected = case["expected_behavior"]
    score = CaseScore(
        case_id=case["id"],
        expected_behavior=expected,
        mode=result.mode,
        latency_s=latency,
    )

    expected_refs = set(case.get("expected_source_ref") or [])
    if expected_refs:
        retrieved_docs = {s.doc_id for s in result.sources[:10]}
        score.recall_at_10 = bool(expected_refs & retrieved_docs)

    if expected == "answer":
        # citation accuracy: displayed, verifier-passed citations point into
        # the expected sources
        passed_cites = [c for c in result.citations if c["passed"]]
        score.citation_ok = bool(passed_cites) and all(
            c["doc_id"] in expected_refs for c in passed_cites
        )
        # displayed-quote integrity: synthesized answers must carry verified
        # quotes; raw_passages/abstained display no quotes (verifier caught it)
        score.quote_integrity_ok = (
            bool(result.verification.get("integrity"))
            if result.mode == "synthesized"
            else result.mode in {"raw_passages", "abstained"}
        )
        if result.mode == "synthesized":
            if grader == "model":
                score.grounded, score.element_hits = grade_case_model(case, result, engine.chat)
            else:
                score.grounded, score.element_hits = grade_case_keyword(case, result)
        else:
            score.grounded = False
            score.notes = f"expected an answer, got mode={result.mode}"
    else:  # expected abstain
        score.honest_abstention = result.abstained or result.mode == "abstained"
        if not score.honest_abstention:
            score.notes = "improvised instead of abstaining"

    return score


def _rate(values: list[bool | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def aggregate(scores: list[CaseScore]) -> dict[str, float | None]:
    return {
        "retrieval_recall_at_10": _rate([s.recall_at_10 for s in scores]),
        "citation_accuracy": _rate([s.citation_ok for s in scores]),
        "verbatim_quote_integrity": _rate([s.quote_integrity_ok for s in scores]),
        "grounded_answer_rate": _rate([s.grounded for s in scores]),
        "honest_abstention_rate": _rate([s.honest_abstention for s in scores]),
        "latency_seconds_max": max((s.latency_s for s in scores), default=0.0),
    }


def gate(metrics: dict[str, float | None], thresholds: dict[str, float]) -> list[str]:
    """Returns the list of threshold breaches (empty = pass)."""
    breaches = []
    for name, floor in thresholds.items():
        value = metrics.get(name)
        if value is None:
            continue
        if name == "latency_seconds_max":
            if value > floor:
                breaches.append(f"{name}: {value:.1f}s > limit {floor}s")
        elif value < floor:
            breaches.append(f"{name}: {value:.3f} < threshold {floor}")
    return breaches


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def run(argv: list[str] | None = None, engine: AnswerEngine | None = None) -> int:
    parser = argparse.ArgumentParser(description="EMKA gold-standard eval harness")
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--grader", choices=["keyword", "model"], default="keyword")
    parser.add_argument("--report-only", action="store_true", help="never gate (exit 0)")
    parser.add_argument("--only", default="", help="comma-separated case ids")
    args = parser.parse_args(argv)

    metadata, cases = load_cases(Path(args.cases))
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    cfg = load_config()
    engine = engine or AnswerEngine(cfg)
    stub_mode = getattr(engine.chat, "backend", "") == "stub"

    print(f"EMKA eval — {len(cases)} cases, grader={args.grader}")
    if stub_mode:
        print(
            "*** STUB MODELS ACTIVE: scores exercise mechanics only and are NOT "
            "meaningful quality numbers. Run on a provisioned device to gate. ***"
        )

    scores = [score_case(c, engine, args.grader) for c in cases]
    metrics = aggregate(scores)
    thresholds = metadata.get("thresholds", {})
    breaches = gate(metrics, thresholds)

    report = {
        "metadata": {
            "cases_version": metadata.get("version"),
            "n_cases": len(cases),
            "grader": args.grader,
            "stub_models": stub_mode,
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "breaches": breaches,
        "cases": [asdict(s) for s in scores],
    }
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.data_dir / "eval_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nmetric                        value    threshold")
    for name, floor in thresholds.items():
        value = metrics.get(name)
        shown = "n/a  " if value is None else f"{value:.3f}"
        print(f"  {name:<28} {shown}    {floor}")
    for b in breaches:
        print(f"  BREACH: {b}")
    print(f"\nreport -> {out}")

    if args.report_only or not breaches:
        return 0
    return 1


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
