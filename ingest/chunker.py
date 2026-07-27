"""Paragraph-level chunking with exact canonical-text offsets.

Rules (DESIGN.md §5):
- chunks are contiguous slices of the canonical text (~200–500 est. tokens),
  built from whole paragraphs, with one-paragraph overlap between chunks;
- tables and dosing/algorithm blocks are ATOMIC — detected heuristically,
  merged when adjacent, and never split even when oversized;
- every chunk records the breadcrumb in effect at its start and the 1-based
  page its first character falls on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ingest.breadcrumbs import BreadcrumbTracker
from ingest.extract import ExtractedDoc

TARGET_MIN_TOKENS = 200
TARGET_MAX_TOKENS = 500

_DOSE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|mL|ml|L|units?|IU|mEq)\b|\bmg/kg\b", re.IGNORECASE
)
_ROUTE_FREQ = re.compile(
    r"\b(?:IV|IM|IO|PO|SL|PR|SQ|SC|q\d+\s*h|q\d+-\d+\s*h|PRN|bolus|infusion|drip)\b"
)
_COLUMNS = re.compile(r"\S(?:  +|\t)\S")  # 2+ spaces or tab between tokens
_STEP = re.compile(r"^\s*(?:step\s*\d+|\d+[.)]\s+\S|[-•►→]\s+\S)", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text.split()) * 1.3))


@dataclass
class Paragraph:
    text: str
    start: int
    end: int
    atomic: bool


@dataclass
class RawChunk:
    text: str
    char_start: int
    char_end: int
    page: int
    breadcrumb: str
    is_atomic: bool
    token_est: int


def _is_atomic_block(text: str) -> bool:
    """Heuristic: dosing tables, column-formatted tables, and step algorithms
    must never be split mid-block."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    dose_lines = sum(1 for ln in lines if _DOSE.search(ln) or _ROUTE_FREQ.search(ln))
    column_lines = sum(1 for ln in lines if _COLUMNS.search(ln))
    step_lines = sum(1 for ln in lines if _STEP.match(ln))
    return (
        dose_lines >= 2 or column_lines >= 3 or (step_lines >= 3 and step_lines >= len(lines) * 0.6)
    )


def _split_paragraphs(text: str) -> list[Paragraph]:
    """Blank-line/page-break separated paragraphs with exact offsets."""
    paras: list[Paragraph] = []
    for m in re.finditer(r"[^\n\f]+(?:\n(?![ \t]*(?:\n|\f|$))[^\n\f]+)*", text):
        body = m.group(0)
        # trim trailing whitespace inside the match without losing offsets
        end = m.start() + len(body.rstrip())
        start = m.start() + (len(body) - len(body.lstrip()))
        if end > start:
            paras.append(Paragraph(text[start:end], start, end, False))
    return paras


def _split_oversized(p: Paragraph, canonical: str) -> list[Paragraph]:
    """Sentence-split a huge NON-atomic paragraph, preserving exact offsets."""
    if p.atomic or estimate_tokens(p.text) <= TARGET_MAX_TOKENS:
        return [p]
    pieces: list[Paragraph] = []
    current_start = p.start
    for m in _SENTENCE_END.finditer(canonical, p.start, p.end):
        candidate = canonical[current_start : m.start()]
        if estimate_tokens(candidate) >= TARGET_MAX_TOKENS:
            pieces.append(Paragraph(candidate, current_start, m.start(), False))
            current_start = m.end()
    if current_start < p.end:
        pieces.append(Paragraph(canonical[current_start : p.end], current_start, p.end, False))
    return pieces or [p]


def _merge_adjacent_atomic(paras: list[Paragraph]) -> list[Paragraph]:
    """A table split by blank lines is still one table."""
    merged: list[Paragraph] = []
    for p in paras:
        if merged and merged[-1].atomic and p.atomic:
            prev = merged[-1]
            # only merge if truly adjacent (whitespace/page-break gap only)
            merged[-1] = Paragraph(
                text="",  # filled from canonical below by caller
                start=prev.start,
                end=p.end,
                atomic=True,
            )
        else:
            merged.append(Paragraph(p.text, p.start, p.end, p.atomic))
    return merged


def _mark_atomic_row_runs(paras: list[Paragraph]) -> None:
    """Real PDFs often extract each table row as its own one-line block.
    Two or more consecutive row-looking one-liners form an atomic run."""

    def rowish(p: Paragraph) -> bool:
        lines = [ln for ln in p.text.splitlines() if ln.strip()]
        return len(lines) == 1 and bool(
            _DOSE.search(p.text) or _ROUTE_FREQ.search(p.text) or _COLUMNS.search(p.text)
        )

    i = 0
    while i < len(paras):
        if rowish(paras[i]):
            j = i
            while j + 1 < len(paras) and rowish(paras[j + 1]):
                j += 1
            if j > i:
                for k in range(i, j + 1):
                    paras[k].atomic = True
            i = j + 1
        else:
            i += 1


def chunk_document(doc: ExtractedDoc, pub_number: str) -> list[RawChunk]:
    canonical = doc.text
    paras = _split_paragraphs(canonical)
    for p in paras:
        p.atomic = _is_atomic_block(p.text)
    _mark_atomic_row_runs(paras)
    paras = _merge_adjacent_atomic(paras)
    for p in paras:
        p.text = canonical[p.start : p.end]
    paras = [piece for p in paras for piece in _split_oversized(p, canonical)]

    tracker = BreadcrumbTracker(pub_number)
    chunks: list[RawChunk] = []
    group: list[Paragraph] = []
    group_has_body = False
    group_breadcrumb = tracker.breadcrumb()

    def flush() -> None:
        if not group:
            return
        start, end = group[0].start, group[-1].end
        text = canonical[start:end]
        page = doc.page_for_offset(start)
        chunks.append(
            RawChunk(
                text=text,
                char_start=start,
                char_end=end,
                page=page,
                breadcrumb=f"{group_breadcrumb} > p.{page}",
                is_atomic=any(p.atomic for p in group),
                token_est=estimate_tokens(text),
            )
        )

    for p in paras:
        recognized = [tracker.observe_line(line) for line in p.text.splitlines()]
        nonempty_lines = sum(1 for line in p.text.splitlines() if line.strip())
        is_heading_para = any(recognized) and nonempty_lines == 1

        current = estimate_tokens(canonical[group[0].start : group[-1].end]) if group else 0
        incoming = estimate_tokens(p.text)

        # Section alignment beats size: a heading always starts a new chunk
        # once the current one has body content, keeping breadcrumbs exact.
        if group and is_heading_para and group_has_body:
            flush()
            group, group_has_body = [], False
        # Size-based flush, with one-paragraph overlap carried forward
        # (overlap only within a section; never carry an atomic block).
        elif group and (current + incoming > TARGET_MAX_TOKENS or p.atomic):
            flush()
            last = group[-1]
            carry = (
                not p.atomic
                and not last.atomic
                and estimate_tokens(last.text) + incoming <= TARGET_MAX_TOKENS
            )
            group = [last] if carry else []
            group_has_body = carry

        if not group:
            group_breadcrumb = tracker.breadcrumb()
        group.append(p)
        # A heading arriving before the group has any body content refines the
        # breadcrumb the not-yet-emitted chunk will carry. Without this, a
        # chapter title immediately followed by its first subsection (no body
        # between) would drop the subsection level — e.g. "Ch 3 > p.1" instead
        # of "Ch 3 > 3.1 > p.1". Consecutive headings: the deepest one wins.
        if is_heading_para and not group_has_body:
            group_breadcrumb = tracker.breadcrumb()
        group_has_body = group_has_body or not is_heading_para

        # an atomic block always terminates its chunk
        if p.atomic:
            flush()
            group, group_has_body = [], False
    flush()
    return chunks
