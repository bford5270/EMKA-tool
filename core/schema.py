"""The chunk schema — the contract every downstream component binds to.

FROZEN as of Prompt 3. Changes require a migration proposal in DESIGN.md §5.

Offset semantics (the verification layer depends on this exactly):

- ``ingest.extract.extract_document`` produces the document's CANONICAL TEXT:
  each page's layout-sorted text, pages joined by a single form feed ("\\f").
  Extraction is deterministic for a given PDF + extractor version.
- ``char_start``/``char_end`` are Python character offsets into that canonical
  text, such that ``canonical_text[char_start:char_end] == chunk.text``.
  (The playbook says "byte offsets"; we standardize on character offsets
  because they are what Python slicing verifies natively — UTF-8 byte offsets
  are derivable from them deterministically. Recorded as a deliberate
  deviation in DESIGN.md §5.)
- ``page`` is the 1-based PDF page on which ``char_start`` falls.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

CHUNK_SCHEMA_VERSION = "1.0"

AUTHORITY_TIERS = ("T1", "T2", "T3", "T4", "T5")
SHELVES = ("authoritative", "unit")


@dataclass(frozen=True)
class DocMeta:
    """Manifest-sourced metadata shared by every chunk of a document."""

    doc_id: str  # manifest Ref ID, e.g. "CPG-03"
    title: str
    pub_number: str  # e.g. "NTTP 4-02", or the CPG id, e.g. "JTS CPG 18"
    edition_date: str  # as printed on the pub, e.g. "12 Jul 2019"
    authority_tier: str  # T1..T5 (see DESIGN.md §3)
    shelf: str  # authoritative | unit
    distribution_stmt: str  # e.g. "DISTRIBUTION A"
    category: str  # manifest category, e.g. "Blood / Resuscitation"
    rights_posture: str  # e.g. "USG", "©-LIC", "VERIFY"

    def __post_init__(self) -> None:
        if self.authority_tier not in AUTHORITY_TIERS:
            raise ValueError(f"invalid authority_tier {self.authority_tier!r}")
        if self.shelf not in SHELVES:
            raise ValueError(f"invalid shelf {self.shelf!r}")


@dataclass(frozen=True)
class Chunk:
    """One retrievable, citable unit of source text. THE frozen contract."""

    # identity
    chunk_id: str  # f"{doc_id}:{seq:05d}"
    doc_id: str
    seq: int  # 0-based position within the document

    # document metadata (denormalized from DocMeta for self-contained chunks)
    title: str
    pub_number: str
    edition_date: str
    authority_tier: str  # T1..T5
    shelf: str  # authoritative | unit
    distribution_stmt: str
    category: str
    rights_posture: str
    source_sha256: str  # sha256 of the source PDF file

    # location / citation
    page: int  # 1-based PDF page where the chunk starts
    char_start: int  # offset into the canonical extracted text
    char_end: int
    breadcrumb: str  # e.g. "NTTP 4-02 > Ch 3 > 3.2.1 > p.37"

    # content
    text: str  # exact canonical-text slice (verbatim source of truth)
    is_atomic: bool  # table / dosing / algorithm block — never split
    token_est: int  # rough token estimate used by the chunker

    schema_version: str = CHUNK_SCHEMA_VERSION

    @property
    def embed_text(self) -> str:
        """Text as indexed for retrieval: breadcrumb context + verbatim body.
        Retrieval indexes THIS; verification always checks ``text``."""
        return f"{self.breadcrumb}\n{self.text}"

    @property
    def citation(self) -> str:
        """Human-facing pinpoint citation."""
        return f"{self.pub_number} ({self.edition_date}), {self.breadcrumb}"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> Chunk:
        data = json.loads(line)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
