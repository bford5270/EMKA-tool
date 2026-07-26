"""``make ingest`` entry point: manifest -> queue -> chunks -> log.

Fully offline. Reads docs/EMKA_Corpus_Manifest.xlsx and corpus/, writes
chunk JSONL + ingest log under data/. Never modifies the manifest.
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.config import REPO_ROOT, load_config
from ingest.ingest_log import IngestLog
from ingest.manifest import load_manifest
from ingest.pipeline import ingest_pdf, persist_chunks
from ingest.queue import build_queue, row_to_docmeta

MANIFEST_PATH = REPO_ROOT / "docs" / "EMKA_Corpus_Manifest.xlsx"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    phases = ("0",)
    if "--all-phases" in argv:
        phases = ("0", "1", "2")

    cfg = load_config()
    rows = load_manifest(MANIFEST_PATH)
    report = build_queue(rows, Path(cfg.corpus_dir), phases=phases)

    print(f"EMKA ingest — manifest rows: {len(rows)}")
    print(report.summary())

    log = IngestLog(cfg.data_dir / "ingest-log.sqlite")
    failures = 0
    for row, pdf_path in report.matched:
        prior = log.latest(row.ref_id)
        try:
            chunks, result = ingest_pdf(pdf_path, row_to_docmeta(row))
            if prior and prior["sha256"] == result.sha256 and prior["status"] == "ingested":
                print(f"  = {row.ref_id}: unchanged ({result.sha256[:12]}…), skipping")
                continue
            persist_chunks(chunks, result, cfg)
            log.record(
                row.ref_id,
                "ingested",
                sha256=result.sha256,
                n_chunks=result.n_chunks,
                n_pages=result.n_pages,
            )
            ocr_note = (
                f" [OCR MISSING on pages {result.ocr_missing_pages}]"
                if result.ocr_missing_pages
                else ""
            )
            print(f"  + {row.ref_id}: {result.n_chunks} chunks / {result.n_pages} pages{ocr_note}")
        except Exception as e:  # noqa: BLE001 — one bad PDF must not kill the run
            failures += 1
            log.record(row.ref_id, "failed", error=str(e))
            print(f"  ! {row.ref_id}: FAILED — {e}")
    for row in report.rights_gated:
        log.record(row.ref_id, "rights-gated-skipped")
    log.close()

    print(f"\nDone. failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
