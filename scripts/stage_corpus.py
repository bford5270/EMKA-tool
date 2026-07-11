"""Stage a JTS CPG zip (or a directory of PDFs) into corpus/authoritative/.

The official JTS bundles (jts.health.mil, "Zip of Current JTS CPGs A-H / I-Z")
name files like:

    Damage_Control_Resuscitation_12_Jul_2019_ID18.pdf

while the ingest queue matches on manifest Ref IDs (CPG-03.pdf or
CPG-03__slug.pdf — see corpus/README.md). This tool closes that gap:

    uv run python scripts/stage_corpus.py ~/Downloads/Zip_of_Current_JTS_CPGs_A-H.zip
    uv run python scripts/stage_corpus.py ~/Downloads/cpgs/ --dry-run

Each PDF's filename is matched against manifest titles by token overlap
(Jaccard over normalized content words; dates/IDs stripped). A file is staged
only when the best match is strong AND clearly beats the runner-up —
ambiguous or unmatched files are LISTED for manual placement, never guessed.
Nothing is ever deleted; existing staged files are only overwritten with
--force.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import REPO_ROOT, load_config  # noqa: E402
from ingest.manifest import ManifestRow, load_manifest  # noqa: E402

MANIFEST_PATH = REPO_ROOT / "docs" / "EMKA_Corpus_Manifest.xlsx"

MIN_SCORE = 0.55  # best match must be at least this similar
MIN_MARGIN = 0.15  # ...and beat the runner-up by at least this much

_MONTHS = {
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "sept",
    "oct",
    "nov",
    "dec",
}
_NOISE = {"the", "a", "an", "of", "in", "for", "and", "to", "or", "on", "cpg", "jts", "id"}


def normalize_tokens(text: str) -> frozenset[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return frozenset(t for t in tokens if t not in _NOISE and t not in _MONTHS and not t.isdigit())


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


@dataclass
class MatchResult:
    pdf: Path
    ref_id: str | None
    title: str = ""
    score: float = 0.0
    runner_up: str = ""
    reason: str = ""  # "" = matched; else why it was not staged


def match_pdfs(
    pdfs: list[Path], rows: list[ManifestRow]
) -> tuple[list[MatchResult], list[MatchResult]]:
    """Returns (matched, unmatched_or_ambiguous)."""
    candidates = [(r, normalize_tokens(r.title)) for r in rows if r.shelf == "authoritative"]
    matched: list[MatchResult] = []
    skipped: list[MatchResult] = []
    for pdf in sorted(pdfs):
        file_tokens = normalize_tokens(pdf.stem)
        scored = sorted(
            ((jaccard(file_tokens, tokens), row) for row, tokens in candidates),
            key=lambda x: x[0],
            reverse=True,
        )
        best_score, best_row = scored[0]
        second_score, second_row = scored[1] if len(scored) > 1 else (0.0, None)
        result = MatchResult(
            pdf=pdf,
            ref_id=best_row.ref_id,
            title=best_row.title,
            score=best_score,
            runner_up=f"{second_row.ref_id} ({second_score:.2f})" if second_row else "",
        )
        if best_score < MIN_SCORE:
            result.ref_id = None
            result.reason = f"no manifest title close enough (best {best_score:.2f})"
            skipped.append(result)
        elif best_score - second_score < MIN_MARGIN:
            result.ref_id = None
            result.reason = f"ambiguous: {best_row.ref_id} ({best_score:.2f}) vs {result.runner_up}"
            skipped.append(result)
        else:
            matched.append(result)
    return matched, skipped


def collect_pdfs(source: Path, workdir: Path) -> list[Path]:
    if source.is_dir():
        return list(source.rglob("*.pdf")) + list(source.rglob("*.PDF"))
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as z:
            z.extractall(workdir)
        return list(Path(workdir).rglob("*.pdf")) + list(Path(workdir).rglob("*.PDF"))
    if source.suffix.lower() == ".pdf":
        return [source]
    raise SystemExit(f"unsupported source: {source} (need a .zip, a directory, or a .pdf)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("source", help="JTS zip file, a directory of PDFs, or a single PDF")
    parser.add_argument("--dest", default=None, help="default: <corpus_dir>/authoritative")
    parser.add_argument("--dry-run", action="store_true", help="report matches, copy nothing")
    parser.add_argument("--force", action="store_true", help="overwrite already-staged files")
    args = parser.parse_args()

    cfg = load_config()
    dest = Path(args.dest) if args.dest else cfg.corpus_dir / "authoritative"
    rows = load_manifest(MANIFEST_PATH)

    with tempfile.TemporaryDirectory() as workdir:
        pdfs = collect_pdfs(Path(args.source).expanduser(), Path(workdir))
        if not pdfs:
            print("no PDFs found in source")
            return 1
        matched, skipped = match_pdfs(pdfs, rows)

        print(f"{len(pdfs)} PDFs -> matched {len(matched)}, needs-review {len(skipped)}\n")
        staged = already = 0
        for m in matched:
            target = dest / f"{m.ref_id}__{m.pdf.stem}.pdf"
            marker = " (dry-run)" if args.dry_run else ""
            if target.exists() and not args.force:
                already += 1
                print(f"  = {m.ref_id:<8} already staged: {target.name}")
                continue
            print(f"  + {m.ref_id:<8} {m.pdf.name}  ->  {target.name}  [{m.score:.2f}]{marker}")
            if not args.dry_run:
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(m.pdf, target)
                staged += 1
        if skipped:
            print("\nNEEDS MANUAL REVIEW (not staged — place by hand per corpus/README.md):")
            for m in skipped:
                print(f"  ? {m.pdf.name}\n      {m.reason}")

    print(
        f"\nstaged={staged} already-present={already} needs-review={len(skipped)}"
        + ("" if args.dry_run else "\nnext: make ingest && make index && make eval")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
