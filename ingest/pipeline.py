"""Ingest one PDF into cited chunks + persist as JSONL with an ingest manifest.

Outputs (under EMKA_DATA_DIR, default ./data — gitignored, device-local):

    data/chunks/<doc_id>.jsonl      one Chunk per line (core/schema.py)
    data/ingest_manifest.json       {doc_id: {sha256, status, n_chunks, ...}}
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from core.config import EmkaConfig, load_config
from core.schema import Chunk, DocMeta
from ingest.chunker import chunk_document
from ingest.extract import extract_document


@dataclass
class IngestResult:
    doc_id: str
    status: str  # ingested | failed
    sha256: str = ""
    n_chunks: int = 0
    n_pages: int = 0
    ocr_missing_pages: list[int] = field(default_factory=list)
    error: str = ""
    chunks_path: str = ""


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ingest_pdf(pdf_path: str | Path, meta: DocMeta) -> tuple[list[Chunk], IngestResult]:
    """Extract, chunk, and wrap a single PDF. Pure function of (file, meta)."""
    pdf_path = Path(pdf_path)
    digest = sha256_file(pdf_path)
    extracted = extract_document(pdf_path)
    raw_chunks = chunk_document(extracted, meta.pub_number)

    chunks = [
        Chunk(
            chunk_id=f"{meta.doc_id}:{seq:05d}",
            doc_id=meta.doc_id,
            seq=seq,
            title=meta.title,
            pub_number=meta.pub_number,
            edition_date=meta.edition_date,
            authority_tier=meta.authority_tier,
            shelf=meta.shelf,
            distribution_stmt=meta.distribution_stmt,
            category=meta.category,
            rights_posture=meta.rights_posture,
            source_sha256=digest,
            page=rc.page,
            char_start=rc.char_start,
            char_end=rc.char_end,
            breadcrumb=rc.breadcrumb,
            text=rc.text,
            is_atomic=rc.is_atomic,
            token_est=rc.token_est,
        )
        for seq, rc in enumerate(raw_chunks)
    ]
    result = IngestResult(
        doc_id=meta.doc_id,
        status="ingested",
        sha256=digest,
        n_chunks=len(chunks),
        n_pages=len(extracted.pages),
        ocr_missing_pages=extracted.ocr_missing_pages,
    )
    return chunks, result


def persist_chunks(
    chunks: list[Chunk], result: IngestResult, cfg: EmkaConfig | None = None
) -> Path:
    cfg = cfg or load_config()
    chunks_dir = cfg.data_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    out = chunks_dir / f"{result.doc_id}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(c.to_json() + "\n")
    result.chunks_path = str(out)

    manifest_path = cfg.data_dir / "ingest_manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[result.doc_id] = {
        "sha256": result.sha256,
        "status": result.status,
        "n_chunks": result.n_chunks,
        "n_pages": result.n_pages,
        "ocr_missing_pages": result.ocr_missing_pages,
        "chunks_path": result.chunks_path,
        "error": result.error,
        "ingested_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def load_chunks(doc_id: str, cfg: EmkaConfig | None = None) -> list[Chunk]:
    cfg = cfg or load_config()
    path = cfg.data_dir / "chunks" / f"{doc_id}.jsonl"
    with open(path, encoding="utf-8") as f:
        return [Chunk.from_json(line) for line in f if line.strip()]


def load_all_chunks(cfg: EmkaConfig | None = None) -> list[Chunk]:
    cfg = cfg or load_config()
    chunks_dir = cfg.data_dir / "chunks"
    out: list[Chunk] = []
    if chunks_dir.exists():
        for path in sorted(chunks_dir.glob("*.jsonl")):
            with open(path, encoding="utf-8") as f:
                out.extend(Chunk.from_json(line) for line in f if line.strip())
    return out
