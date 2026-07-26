"""Machine-parsable prompt block format shared by the orchestrator, the
stub chat backend, and tests. Version-locked alongside the synthesis prompt."""

from __future__ import annotations

import re
from pathlib import Path

from capability.loadout import AvailabilityFinding
from retrieval.search import RetrievedChunk

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SYNTHESIS_PROMPT_VERSION = "synthesis_v1"

_TIER_ORDER = {"T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5}

PASSAGE_RE = re.compile(
    r"\[PASSAGE chunk_id=(?P<chunk_id>\S+) [^\]]*\]\n(?P<body>.*?)\n\[/PASSAGE\]",
    re.DOTALL,
)
CONFLICT_RE = re.compile(r"<conflict\s+chunks=\"([^\"]+)\"\s*>(.*?)</conflict>", re.DOTALL)


def load_system_prompt(version: str = SYNTHESIS_PROMPT_VERSION) -> str:
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def order_by_precedence(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Authority tier first (T1 highest), then recency hint (edition string
    sorts are best-effort), then rerank score."""
    return sorted(
        chunks,
        key=lambda rc: (
            _TIER_ORDER.get(rc.chunk.authority_tier, 9),
            -rc.rerank_score,
        ),
    )


def format_passage(rc: RetrievedChunk) -> str:
    c = rc.chunk
    return (
        f"[PASSAGE chunk_id={c.chunk_id} pub={c.pub_number!r} edition={c.edition_date!r} "
        f"tier={c.authority_tier} shelf={c.shelf} cite={c.breadcrumb!r} page={c.page}]\n"
        f"{c.text}\n"
        f"[/PASSAGE]"
    )


def format_availability(findings: list[AvailabilityFinding]) -> str:
    if not findings:
        return ""
    lines = ["[AVAILABILITY command-provided, unit-shelf, not custodian-verified]"]
    for f in findings:
        status = (
            "NOT in loadout"
            if f.available is False
            else ("in loadout" if f.available else "availability unknown")
        )
        stale = " (AS-OF DATE STALE)" if f.stale else ""
        lines.append(
            f"- {f.matched_name} ({f.kind}, {f.role}): {status}; "
            f"as-of {f.as_of}, source: {f.source}{stale}"
        )
    lines.append("[/AVAILABILITY]")
    return "\n".join(lines)


def build_user_message(
    question: str,
    ordered: list[RetrievedChunk],
    findings: list[AvailabilityFinding],
) -> str:
    parts = ["SOURCE PASSAGES (ordered by authority tier, then relevance):\n"]
    parts += [format_passage(rc) for rc in ordered]
    availability = format_availability(findings)
    if availability:
        parts.append("\n" + availability)
    parts.append(f"\nQUESTION: {question}")
    return "\n\n".join(parts)


def parse_conflicts(answer_text: str) -> list[dict]:
    return [
        {"chunk_ids": [c.strip() for c in m.group(1).split(",")], "description": m.group(2).strip()}
        for m in CONFLICT_RE.finditer(answer_text)
    ]


def strip_conflict_tags(answer_text: str) -> str:
    return CONFLICT_RE.sub(lambda m: m.group(2).strip(), answer_text)
