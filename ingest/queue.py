"""Manifest rows -> ingest work queue.

FILENAME CONVENTION (documented contract, see also corpus/README.md):
a manifest row matches a PDF in ``corpus/<shelf>/`` when the filename is

    <Ref ID>.pdf                          e.g. CPG-03.pdf
    <Ref ID>__<anything>.pdf              e.g. CPG-03__Damage_Control_Resuscitation.pdf

Matching is case-insensitive on the Ref ID; the double underscore separates
the id from an optional human-readable slug. Anything else in corpus/ is
ignored (and reported as unmatched-file so typos are visible).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.schema import DocMeta
from ingest.manifest import ManifestRow


@dataclass
class QueueReport:
    matched: list[tuple[ManifestRow, Path]] = field(default_factory=list)
    missing_file: list[ManifestRow] = field(default_factory=list)
    rights_gated: list[ManifestRow] = field(default_factory=list)  # listed, SKIPPED
    out_of_scope: list[ManifestRow] = field(default_factory=list)  # phase/shelf filtered
    unmatched_files: list[Path] = field(default_factory=list)  # files matching no row

    def summary(self) -> str:
        lines = [
            f"matched      : {len(self.matched)}",
            f"missing-file : {len(self.missing_file)}",
            f"rights-gated : {len(self.rights_gated)} (listed, SKIPPED)",
            f"out-of-scope : {len(self.out_of_scope)} (phase/shelf filter)",
            f"unmatched files in corpus/: {len(self.unmatched_files)}",
        ]
        if self.rights_gated:
            lines.append("rights-gated rows:")
            lines += [f"  - {r.ref_id}  {r.title}  [{r.rights}]" for r in self.rights_gated]
        if self.missing_file:
            lines.append("missing files:")
            lines += [f"  - {r.ref_id}  {r.title}" for r in self.missing_file]
        return "\n".join(lines)


def _index_corpus_files(shelf_dir: Path) -> dict[str, Path]:
    """ref-id (lowercased) -> file path, per the filename convention."""
    index: dict[str, Path] = {}
    if shelf_dir.exists():
        for path in sorted(shelf_dir.glob("*.pdf")):
            stem = path.stem
            ref = stem.split("__", 1)[0].strip().lower()
            index.setdefault(ref, path)
    return index


def build_queue(
    rows: list[ManifestRow],
    corpus_dir: Path,
    phases: tuple[str, ...] = ("0",),
    shelves: tuple[str, ...] = ("authoritative",),
) -> QueueReport:
    """First build: Phase '0 — Core', authoritative shelf only."""
    report = QueueReport()
    claimed: set[Path] = set()
    shelf_dirs = {
        "authoritative": corpus_dir / "authoritative",
        "unit": corpus_dir / "unit",
    }
    indexes = {shelf: _index_corpus_files(d) for shelf, d in shelf_dirs.items()}

    for row in rows:
        if row.phase not in phases or row.shelf not in shelves:
            report.out_of_scope.append(row)
            continue
        if row.rights_gated:
            report.rights_gated.append(row)
            continue
        index = indexes.get(row.shelf, {})
        path = index.get(row.ref_id.lower())
        if path is None:
            report.missing_file.append(row)
        else:
            report.matched.append((row, path))
            claimed.add(path)

    all_refs = {r.ref_id.lower() for r in rows}
    for _shelf, index in indexes.items():
        for ref, path in index.items():
            if path not in claimed and ref not in all_refs:
                report.unmatched_files.append(path)
    return report


def row_to_docmeta(row: ManifestRow) -> DocMeta:
    """Manifest row -> chunk-level metadata. pub_number uses the Ref ID —
    short, unique, and stable across editions — while the full title rides
    along in ``title`` (decision recorded in DESIGN.md §5)."""
    return DocMeta(
        doc_id=row.ref_id,
        title=row.title,
        pub_number=row.ref_id,
        edition_date=row.edition_date,
        authority_tier=row.tier,
        shelf="unit" if row.shelf == "unit" else "authoritative",
        distribution_stmt="",  # not tracked in the manifest; set at custodian review
        category=row.category,
        rights_posture=row.rights,
    )
