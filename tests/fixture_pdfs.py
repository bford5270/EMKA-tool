"""Deterministic doctrine-style PDF fixtures for golden ingestion tests.

This session's build environment cannot reach jts.health.mil, so golden tests
run against synthetic PDFs that mimic JTS CPG structure: chapter headings,
decimal-numbered sections, flowing paragraphs, and a dosing table that must
survive chunking intact. On a box with the real corpus staged, the same tests
can be pointed at a real CPG via EMKA_GOLDEN_PDF (see test_ingest_golden.py).
"""

from __future__ import annotations

from pathlib import Path

import fitz

BODY = 11
HEAD = 14

PAGE1 = [
    (HEAD, "CHAPTER 3"),
    (HEAD, "3.1 Purpose"),
    (
        BODY,
        "This Clinical Practice Guideline describes damage control resuscitation "
        "principles for the deployed environment. It applies to Role 1 through "
        "Role 3 facilities and emphasizes early hemorrhage control, balanced "
        "blood product resuscitation, and prevention of hypothermia, acidosis, "
        "and coagulopathy.",
    ),
    (
        BODY,
        "Casualties presenting with hemorrhagic shock require immediate "
        "intervention. The primary goals are to stop bleeding, restore "
        "circulating volume with whole blood or balanced components, and "
        "minimize crystalloid use, which worsens dilutional coagulopathy.",
    ),
    (HEAD, "3.2 Massive Transfusion"),
    (
        BODY,
        "Massive transfusion is defined as transfusion of ten or more units of "
        "red blood cells within twenty-four hours, or replacement of the total "
        "blood volume. Early recognition of casualties likely to require "
        "massive transfusion improves survival.",
    ),
]

PAGE2 = [
    (HEAD, "3.2.1 Tranexamic Acid Administration"),
    (
        BODY,
        "Tranexamic acid should be administered as early as possible and within "
        "three hours of injury for casualties in or at risk of hemorrhagic "
        "shock. Administration after three hours is not recommended.",
    ),
    # dosing table — must remain one atomic chunk
    (
        BODY,
        "Drug            Dose        Route     Frequency\n"
        "TXA             2 g         IV        single bolus over 10 min\n"
        "Calcium         1 g         IV        after first unit of blood\n"
        "Ceftriaxone     1 g         IV        q24h if indicated",
    ),
    (
        BODY,
        "Hypocalcemia is common during resuscitation with stored blood products "
        "and worsens coagulopathy. Ionized calcium should be monitored and "
        "replaced aggressively throughout the resuscitation.",
    ),
]

PAGE3 = [
    (HEAD, "3.3 Whole Blood"),
    (
        BODY,
        "Cold stored low titer group O whole blood is the preferred "
        "resuscitation product in the deployed setting when available. Fresh "
        "whole blood collected from a pre-screened donor pool is an "
        "alternative when cold stored product is exhausted.",
    ),
    (
        BODY,
        "Units without whole blood capability should resuscitate with plasma "
        "and red blood cells in a one to one ratio, adding platelets when "
        "available. Crystalloid should be limited to drug dilution.",
    ),
]

PAGES = [PAGE1, PAGE2, PAGE3]


def build_sample_cpg(path: str | Path) -> Path:
    """Write the deterministic 3-page sample CPG PDF; returns the path."""
    path = Path(path)
    doc = fitz.open()
    for page_items in PAGES:
        page = doc.new_page()  # default Letter-ish A4 size
        y = 72.0
        for size, text in page_items:
            # single-line inserts keep extraction deterministic; wrap long
            # bodies with textbox at fixed width
            box_h = 200.0
            rect = fitz.Rect(72, y, 540, y + box_h)
            leftover = page.insert_textbox(rect, text, fontsize=size, fontname="helv")
            assert leftover >= 0, f"fixture text overflowed its box: {text[:40]!r}"
            y += (box_h - leftover) + 10
    doc.save(str(path))
    doc.close()
    return path
