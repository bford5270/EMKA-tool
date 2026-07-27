"""Verbatim quote verification — the layer that makes citations trustworthy.

The synthesis prompt (generate/prompts/) requires the model to wrap every
verbatim quotation in an explicit tag naming its source chunk:

    <quote src="CPG-03:00001">Tranexamic acid should be administered…</quote>

After synthesis, EVERY tagged span is checked against the cited chunk:

- EXACT: the quote appears character-for-character in ``chunk.text``.
- WS_NORMALIZED: identical after collapsing whitespace runs (PDF extraction
  introduces line breaks mid-sentence; every non-whitespace character must
  still match exactly, in order, contiguously). Recorded as a distinct pass
  mode — a deliberate, documented relaxation (DESIGN.md §6).
- Anything else is a FAIL: not found, altered, or citing an unknown chunk.

When the chunk's document canonical text is available (device has the
corpus), the located span is additionally confirmed at its absolute offsets:
``canonical[chunk.char_start + rel_start : …] == located span`` — the
stored-offset confirmation the playbook requires.

Policy on failure (enforced by generate/answer.py): one regeneration; if the
regenerated answer still fails, return raw retrieved passages with a flag
instead of a synthesized answer. Fail safe, never fabricate.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from core.schema import Chunk

QUOTE_RE = re.compile(r"<quote\s+src=\"([^\"]+)\"\s*>(.*?)</quote>", re.DOTALL)

CanonicalLookup = Callable[[str], str | None]  # doc_id -> canonical text (or None)


class QuoteStatus(StrEnum):
    EXACT = "exact"
    WS_NORMALIZED = "ws_normalized"
    FAIL_NOT_FOUND = "fail_not_found"
    FAIL_UNKNOWN_CHUNK = "fail_unknown_chunk"
    FAIL_OFFSET_MISMATCH = "fail_offset_mismatch"


PASSING = {QuoteStatus.EXACT, QuoteStatus.WS_NORMALIZED}


@dataclass
class QuoteCheck:
    chunk_id: str
    quote: str
    status: QuoteStatus
    # location of the verified span, when found:
    rel_start: int | None = None  # offset within chunk.text
    rel_end: int | None = None
    abs_start: int | None = None  # offset within the document canonical text
    abs_end: int | None = None
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status in PASSING


@dataclass
class VerificationReport:
    checks: list[QuoteCheck] = field(default_factory=list)

    @property
    def n_quotes(self) -> int:
        return len(self.checks)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def integrity(self) -> bool:
        """True iff every quoted span verified. An answer with zero quotes
        has integrity (nothing claimed verbatim, nothing to verify)."""
        return self.n_failed == 0

    def summary(self) -> str:
        return f"{self.n_quotes - self.n_failed}/{self.n_quotes} quotes verified"


def extract_quotes(answer_text: str) -> list[tuple[str, str]]:
    """[(chunk_id, quoted_text)] in order of appearance."""
    return [(m.group(1), m.group(2)) for m in QUOTE_RE.finditer(answer_text)]


def _ws_normalized_find(haystack: str, needle: str) -> tuple[int, int] | None:
    """Locate ``needle`` in ``haystack`` treating any whitespace run as
    equivalent. Returns (start, end) in haystack coordinates, or None.
    Every non-whitespace character must match exactly and contiguously."""
    tokens = needle.split()
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(t) for t in tokens)
    m = re.search(pattern, haystack)
    return (m.start(), m.end()) if m else None


def verify_quote(
    quote: str,
    chunk: Chunk,
    canonical_lookup: CanonicalLookup | None = None,
) -> QuoteCheck:
    check = QuoteCheck(chunk_id=chunk.chunk_id, quote=quote, status=QuoteStatus.FAIL_NOT_FOUND)

    idx = chunk.text.find(quote)
    if idx >= 0:
        check.status = QuoteStatus.EXACT
        check.rel_start, check.rel_end = idx, idx + len(quote)
    else:
        span = _ws_normalized_find(chunk.text, quote)
        if span:
            check.status = QuoteStatus.WS_NORMALIZED
            check.rel_start, check.rel_end = span
        else:
            check.detail = "quoted text does not occur in the cited chunk"
            return check

    check.abs_start = chunk.char_start + check.rel_start
    check.abs_end = chunk.char_start + check.rel_end

    # stored-offset confirmation against the document canonical text
    if canonical_lookup is not None:
        canonical = canonical_lookup(chunk.doc_id)
        if canonical is not None:
            located = chunk.text[check.rel_start : check.rel_end]
            if canonical[check.abs_start : check.abs_end] != located:
                check.status = QuoteStatus.FAIL_OFFSET_MISMATCH
                check.detail = "chunk offsets do not reproduce the span in the source text"
    return check


def verify_answer(
    answer_text: str,
    chunks_by_id: dict[str, Chunk],
    canonical_lookup: CanonicalLookup | None = None,
) -> VerificationReport:
    report = VerificationReport()
    for chunk_id, quote in extract_quotes(answer_text):
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            report.checks.append(
                QuoteCheck(
                    chunk_id=chunk_id,
                    quote=quote,
                    status=QuoteStatus.FAIL_UNKNOWN_CHUNK,
                    detail="answer cited a chunk that was not retrieved",
                )
            )
            continue
        report.checks.append(verify_quote(quote, chunk, canonical_lookup))
    return report
