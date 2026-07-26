"""The answer orchestrator: retrieve -> synthesize -> verify -> assemble.

Returns the structured result contract the API and UI depend on:

    {synthesis, sources[], citations[], conflicts[], capability_notes[],
     verification, abstained, mode, latency_s}

Modes:
    synthesized    verified answer (integrity true)
    raw_passages   verification failed twice -> passages only, flagged
    abstained      retrieval below confidence threshold, or no candidates

Fail-safe policy (DESIGN.md §6): on any quote-verification failure the
synthesis is regenerated ONCE with explicit feedback; if it fails again the
system returns the raw retrieved passages with a flag. Never fabricate.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from capability.loadout import AvailabilityFinding, Loadout, load_loadout
from core.config import EmkaConfig, load_config
from core.models import ChatModel, load_chat_model
from generate.prompt_format import (
    SYNTHESIS_PROMPT_VERSION,
    build_user_message,
    load_system_prompt,
    order_by_precedence,
    parse_conflicts,
)
from generate.verify import CanonicalLookup, VerificationReport, verify_answer
from retrieval.search import HybridRetriever, RetrievalResult

NO_PHI_NOTICE = (
    "EMKA is a reference system. It stores no patient data and must not be "
    "used to record patient-identifying information."
)


@dataclass
class SourcePassage:
    """A retrieved passage as displayed to the user (sources are PRIMARY)."""

    chunk_id: str
    doc_id: str
    title: str
    pub_number: str
    edition_date: str
    authority_tier: str
    shelf: str
    breadcrumb: str
    page: int
    text: str
    citation: str
    rerank_score: float
    unit_watermark: bool  # True -> render "unit-added, not custodian-verified"


@dataclass
class AnswerResult:
    question: str
    mode: str  # synthesized | raw_passages | abstained
    synthesis: str = ""
    sources: list[SourcePassage] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    capability_notes: list[dict] = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    abstained: bool = False
    abstain_reason: str = ""
    retrieval_confidence: float = 0.0
    prompt_version: str = SYNTHESIS_PROMPT_VERSION
    latency_s: float = 0.0
    no_phi_notice: str = NO_PHI_NOTICE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sources(result: RetrievalResult) -> list[SourcePassage]:
    ordered = order_by_precedence(result.chunks)
    return [
        SourcePassage(
            chunk_id=rc.chunk.chunk_id,
            doc_id=rc.chunk.doc_id,
            title=rc.chunk.title,
            pub_number=rc.chunk.pub_number,
            edition_date=rc.chunk.edition_date,
            authority_tier=rc.chunk.authority_tier,
            shelf=rc.chunk.shelf,
            breadcrumb=rc.chunk.breadcrumb,
            page=rc.chunk.page,
            text=rc.chunk.text,
            citation=rc.chunk.citation,
            rerank_score=rc.rerank_score,
            unit_watermark=rc.chunk.shelf == "unit",
        )
        for rc in ordered
    ]


def _citations(report: VerificationReport, by_id: dict) -> list[dict]:
    out = []
    for check in report.checks:
        chunk = by_id.get(check.chunk_id)
        out.append(
            {
                "chunk_id": check.chunk_id,
                "quote": check.quote,
                "status": check.status.value,
                "passed": check.passed,
                "citation": chunk.citation if chunk else "(unknown chunk)",
                "page": chunk.page if chunk else None,
                "doc_id": chunk.doc_id if chunk else None,
                "abs_start": check.abs_start,
                "abs_end": check.abs_end,
            }
        )
    return out


class AnswerEngine:
    def __init__(
        self,
        cfg: EmkaConfig | None = None,
        retriever: HybridRetriever | None = None,
        chat: ChatModel | None = None,
        loadout: Loadout | None = None,
        canonical_lookup: CanonicalLookup | None = None,
    ):
        self.cfg = cfg or load_config()
        self.retriever = retriever or HybridRetriever(self.cfg)
        self.chat = chat or load_chat_model(self.cfg)
        self.loadout = loadout if loadout is not None else load_loadout(self.cfg)
        self.canonical_lookup = canonical_lookup
        self._system_prompt = load_system_prompt()

    def answer(self, question: str, context: dict | None = None) -> AnswerResult:
        t0 = time.perf_counter()
        retrieval = self.retriever.search(question)

        if retrieval.abstained:
            return AnswerResult(
                question=question,
                mode="abstained",
                abstained=True,
                abstain_reason=retrieval.abstain_reason,
                sources=_sources(retrieval),
                retrieval_confidence=retrieval.retrieval_confidence,
                synthesis=(
                    "The loaded corpus does not adequately support an answer to this "
                    f"question ({retrieval.abstain_reason})."
                ),
                latency_s=time.perf_counter() - t0,
            )

        ordered = order_by_precedence(retrieval.chunks)
        by_id = {rc.chunk.chunk_id: rc.chunk for rc in ordered}

        # capability matching runs over the retrieved passages — that is where
        # the recommendations live — plus the question itself
        findings: list[AvailabilityFinding] = []
        if self.loadout is not None:
            corpus_text = question + "\n" + "\n".join(rc.chunk.text for rc in ordered)
            findings = self.loadout.match(corpus_text, context)

        user_message = build_user_message(question, ordered, findings)
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_message},
        ]

        synthesis = self.chat.complete(messages)
        report = verify_answer(synthesis, by_id, self.canonical_lookup)

        if not report.integrity:
            failed = [c for c in report.checks if not c.passed]
            feedback = (
                "VERIFICATION FAILED. These quotes do not match their cited source "
                "character-for-character:\n"
                + "\n".join(f'- src={c.chunk_id}: "{c.quote[:120]}"' for c in failed)
                + "\nRegenerate your answer. Copy quotes EXACTLY from the passages, "
                "or omit the claim."
            )
            synthesis = self.chat.complete(
                messages
                + [
                    {"role": "assistant", "content": synthesis},
                    {"role": "user", "content": feedback},
                ],
                temperature=0.0,
            )
            report = verify_answer(synthesis, by_id, self.canonical_lookup)

        verification = {
            "integrity": report.integrity,
            "summary": report.summary(),
            "checks": [
                {
                    "chunk_id": c.chunk_id,
                    "status": c.status.value,
                    "passed": c.passed,
                    "detail": c.detail,
                }
                for c in report.checks
            ],
        }

        if not report.integrity:
            # fail safe: raw passages, loudly flagged — never a fabricated answer
            return AnswerResult(
                question=question,
                mode="raw_passages",
                synthesis="",
                sources=_sources(retrieval),
                citations=_citations(report, by_id),
                conflicts=[],
                capability_notes=[asdict(f) for f in findings],
                verification=verification,
                retrieval_confidence=retrieval.retrieval_confidence,
                latency_s=time.perf_counter() - t0,
            )

        return AnswerResult(
            question=question,
            mode="synthesized",
            synthesis=synthesis,
            sources=_sources(retrieval),
            citations=_citations(report, by_id),
            conflicts=parse_conflicts(synthesis),
            capability_notes=[asdict(f) for f in findings],
            verification=verification,
            retrieval_confidence=retrieval.retrieval_confidence,
            latency_s=time.perf_counter() - t0,
        )
