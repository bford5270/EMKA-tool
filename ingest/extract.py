"""PDF -> canonical text, page map, and OCR flags.

The canonical text produced here is the string all chunk offsets refer to
(core/schema.py). Determinism matters more than beauty: same PDF + same
extractor version => same canonical text.

OCR: image-only pages are OCR'd via the locally installed ``tesseract``
binary when present (a device provisioning requirement, see DESIGN.md §5);
when it is absent the page is flagged in ``ocr_missing_pages`` and ingestion
continues — a flagged page is a visible defect, not a silent gap.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

PAGE_JOINER = "\f"
# A page with fewer visible characters than this that still contains images
# is treated as image-only and sent to OCR.
OCR_MIN_CHARS = 20


@dataclass
class PageText:
    number: int  # 1-based
    text: str
    char_start: int  # offset of this page's text in the canonical text
    ocr_applied: bool = False
    ocr_missing: bool = False


@dataclass
class ExtractedDoc:
    path: str
    pages: list[PageText] = field(default_factory=list)
    text: str = ""  # canonical text (see core/schema.py)

    @property
    def ocr_missing_pages(self) -> list[int]:
        return [p.number for p in self.pages if p.ocr_missing]

    def page_for_offset(self, offset: int) -> int:
        """1-based page containing a canonical-text offset."""
        page_no = 1
        for p in self.pages:
            if p.char_start > offset:
                break
            page_no = p.number
        return page_no


def _ocr_page(page: fitz.Page) -> str | None:
    """OCR one page with the system tesseract, or None if unavailable."""
    if shutil.which("tesseract") is None:
        return None
    pix = page.get_pixmap(dpi=300)
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        pix.save(tmp.name)
        result = subprocess.run(
            ["tesseract", tmp.name, "stdout", "--psm", "1"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    return result.stdout if result.returncode == 0 else None


def extract_document(pdf_path: str | Path) -> ExtractedDoc:
    """Extract layout-sorted text per page and assemble the canonical text."""
    doc = fitz.open(str(pdf_path))
    extracted = ExtractedDoc(path=str(pdf_path))
    offset = 0
    for i, page in enumerate(doc):
        # sort=True yields reading order (top-to-bottom, left-to-right blocks)
        text = page.get_text("text", sort=True)
        ocr_applied = ocr_missing = False
        if len(text.strip()) < OCR_MIN_CHARS and page.get_images(full=True):
            ocr_text = _ocr_page(page)
            if ocr_text is not None:
                text, ocr_applied = ocr_text, True
            else:
                ocr_missing = True
        extracted.pages.append(
            PageText(
                number=i + 1,
                text=text,
                char_start=offset,
                ocr_applied=ocr_applied,
                ocr_missing=ocr_missing,
            )
        )
        offset += len(text) + len(PAGE_JOINER)
    doc.close()
    extracted.text = PAGE_JOINER.join(p.text for p in extracted.pages)
    return extracted
