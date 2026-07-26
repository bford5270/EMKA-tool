"""Corpus staging tool tests: JTS-style filenames -> manifest Ref IDs.

Uses the REAL manifest so matching quality tracks the actual titles,
including the hardest pair: CPG-03 'Damage Control Resuscitation' vs
CPG-04 'Damage Control Resuscitation in Prolonged Field Care'."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from stage_corpus import MANIFEST_PATH, collect_pdfs, match_pdfs, normalize_tokens

from ingest.manifest import load_manifest

# Realistic JTS bundle filenames (title + date + JTS CPG id)
JTS_STYLE_NAMES = {
    "Damage_Control_Resuscitation_12_Jul_2019_ID18.pdf": "CPG-03",
    "Damage_Control_Resuscitation_Prolonged_Field_Care_01_Oct_2018_ID73.pdf": "CPG-04",
    "Whole_Blood_Transfusion_15_May_2018_ID21.pdf": "CPG-05",
    "Prolonged_Casualty_Care_Guidelines_21_Dec_2021_ID91.pdf": "CPG-02",
}
DECOY = "Canine_Resuscitation_Field_Handbook_2015.pdf"


@pytest.fixture(scope="module")
def rows():
    return load_manifest(MANIFEST_PATH)


def _touch_pdfs(directory: Path, names: list[str]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for n in names:
        p = directory / n
        p.write_bytes(b"%PDF-1.4 test")
        out.append(p)
    return out


def test_normalize_strips_dates_ids_noise():
    tokens = normalize_tokens("Damage_Control_Resuscitation_12_Jul_2019_CPG_ID18")
    assert {"damage", "control", "resuscitation"} <= tokens
    assert not tokens & {"jul", "2019", "12", "cpg"}


def test_jts_filenames_match_correct_ref_ids(rows, tmp_path):
    pdfs = _touch_pdfs(tmp_path, list(JTS_STYLE_NAMES))
    matched, skipped = match_pdfs(pdfs, rows)
    assert not skipped, [s.reason for s in skipped]
    got = {m.pdf.name: m.ref_id for m in matched}
    assert got == JTS_STYLE_NAMES


def test_decoy_is_flagged_not_guessed(rows, tmp_path):
    pdfs = _touch_pdfs(tmp_path, [DECOY])
    matched, skipped = match_pdfs(pdfs, rows)
    assert matched == []
    assert len(skipped) == 1 and skipped[0].ref_id is None


def test_collect_pdfs_from_zip(tmp_path):
    src = tmp_path / "src"
    _touch_pdfs(src, list(JTS_STYLE_NAMES))
    zpath = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for p in src.glob("*.pdf"):
            z.write(p, arcname=f"cpgs/{p.name}")
    work = tmp_path / "work"
    work.mkdir()
    found = collect_pdfs(zpath, work)
    assert len(found) == len(JTS_STYLE_NAMES)


def test_end_to_end_staging_cli(rows, tmp_path, monkeypatch, capsys):
    src = tmp_path / "src"
    _touch_pdfs(src, list(JTS_STYLE_NAMES) + [DECOY])
    dest = tmp_path / "corpus" / "authoritative"
    monkeypatch.setattr(sys, "argv", ["stage_corpus.py", str(src), "--dest", str(dest)])
    from stage_corpus import main

    assert main() == 0
    out = capsys.readouterr().out
    assert "needs-review=1" in out
    staged = sorted(p.name for p in dest.glob("*.pdf"))
    assert staged == [
        "CPG-02__Prolonged_Casualty_Care_Guidelines_21_Dec_2021_ID91.pdf",
        "CPG-03__Damage_Control_Resuscitation_12_Jul_2019_ID18.pdf",
        "CPG-04__Damage_Control_Resuscitation_Prolonged_Field_Care_01_Oct_2018_ID73.pdf",
        "CPG-05__Whole_Blood_Transfusion_15_May_2018_ID21.pdf",
    ]
    # staged names satisfy the ingest queue's filename convention
    from ingest.queue import _index_corpus_files

    index = _index_corpus_files(dest)
    assert set(index) == {"cpg-02", "cpg-03", "cpg-04", "cpg-05"}

    # second run: idempotent, nothing re-copied without --force
    assert main() == 0
    assert "already-present=4" in capsys.readouterr().out
