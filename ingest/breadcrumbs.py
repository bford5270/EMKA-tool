"""Doctrine-numbering -> heading breadcrumb.

Military pubs and CPGs number their structure several ways; we track the
common ones and maintain a heading stack so every text offset can be mapped
to a breadcrumb like ``NTTP 4-02 > Ch 3 > 3.2 > 3.2.1``. The page reference
(``p.N``) is appended per chunk by the chunker, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# "CHAPTER 3" / "Chapter 3 — Casualty Flow"
_CHAPTER = re.compile(r"^\s*CHAPTER\s+(\d+|[IVXLC]+)\b[\s:—–-]*(.*)$", re.IGNORECASE)
# "APPENDIX B" / "Appendix B — AMAL Listing"
_APPENDIX = re.compile(r"^\s*APPENDIX\s+([A-Z])\b[\s:—–-]*(.*)$", re.IGNORECASE)
# Decimal-numbered headings: "3.2 Massive Transfusion", "3.2.1 Ratios"
_DECIMAL = re.compile(r"^\s*(\d+(?:\.\d+)+)\s+(\S.*)$")
# Milpub paragraph numbers: "0302." or "3-7." at line start followed by a title
_MILPARA = re.compile(r"^\s*(\d{4}|\d+-\d+)\.\s+(\S.*)$")

# Headings are short lines; a decimal match inside a flowing sentence is not
# a heading. Guard with a length cap and no terminal period on the title.
_MAX_HEADING_LEN = 90


@dataclass
class _Heading:
    depth: int  # 1 = chapter/appendix, 2+ = numbered levels
    label: str  # e.g. "Ch 3", "3.2.1", "App B"


class BreadcrumbTracker:
    """Feed lines in document order; ask for the breadcrumb at any point."""

    def __init__(self, pub_number: str):
        self.pub_number = pub_number
        self._stack: list[_Heading] = []

    def observe_line(self, line: str) -> bool:
        """Returns True when the line was recognized as a heading."""
        line = line.rstrip()
        if not line or len(line) > _MAX_HEADING_LEN:
            return False

        m = _CHAPTER.match(line)
        if m:
            self._set(_Heading(1, f"Ch {m.group(1)}"))
            return True
        m = _APPENDIX.match(line)
        if m:
            self._set(_Heading(1, f"App {m.group(1).upper()}"))
            return True
        m = _DECIMAL.match(line)
        if m and not m.group(2).rstrip().endswith("."):
            number = m.group(1)
            depth = 1 + number.count(".")  # "3.2" -> depth 2, "3.2.1" -> depth 3
            self._set(_Heading(depth, number))
            return True
        m = _MILPARA.match(line)
        if m and not m.group(2).rstrip().endswith("."):
            self._set(_Heading(2, m.group(1)))
            return True
        return False

    def _set(self, heading: _Heading) -> None:
        self._stack = [h for h in self._stack if h.depth < heading.depth]
        self._stack.append(heading)

    def breadcrumb(self) -> str:
        parts = [self.pub_number] + [h.label for h in self._stack]
        return " > ".join(parts)
