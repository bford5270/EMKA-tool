"""Verification layer unit tests: exact quote must pass, altered must fail."""

from __future__ import annotations

from core.schema import Chunk
from generate.verify import (
    QuoteStatus,
    extract_quotes,
    verify_answer,
    verify_quote,
)

SOURCE_TEXT = (
    "Tranexamic acid should be administered as early as possible and within\n"
    "three hours of injury for casualties in hemorrhagic shock. Administration\n"
    "after three hours is not recommended."
)

CANONICAL = "PREAMBLE " + SOURCE_TEXT + " EPILOGUE"

CHUNK = Chunk(
    chunk_id="CPG-03:00002",
    doc_id="CPG-03",
    seq=2,
    title="DCR",
    pub_number="CPG-03",
    edition_date="12 Jul 2019",
    authority_tier="T3",
    shelf="authoritative",
    distribution_stmt="",
    category="Blood / Resuscitation",
    rights_posture="USG",
    source_sha256="0" * 64,
    page=2,
    char_start=len("PREAMBLE "),
    char_end=len("PREAMBLE ") + len(SOURCE_TEXT),
    breadcrumb="CPG-03 > Ch 3 > 3.2.1 > p.2",
    text=SOURCE_TEXT,
    is_atomic=False,
    token_est=40,
)

LOOKUP = {"CPG-03": CANONICAL}.get


def test_exact_quote_passes():
    quote = "Administration\nafter three hours is not recommended."
    check = verify_quote(quote, CHUNK, LOOKUP)
    assert check.status == QuoteStatus.EXACT and check.passed
    # offsets confirmed against canonical
    assert CANONICAL[check.abs_start : check.abs_end] == quote


def test_ws_normalized_quote_passes_with_distinct_mode():
    quote = "administered as early as possible and within three hours of injury"
    check = verify_quote(quote, CHUNK, LOOKUP)
    assert check.status == QuoteStatus.WS_NORMALIZED and check.passed
    assert "within\nthree" in CANONICAL[check.abs_start : check.abs_end]


def test_deliberately_altered_quote_fails():
    quote = "Tranexamic acid should be administered within six hours of injury"
    check = verify_quote(quote, CHUNK, LOOKUP)
    assert check.status == QuoteStatus.FAIL_NOT_FOUND and not check.passed


def test_subtle_alteration_fails():
    # single word changed: "recommended" -> "advised"
    quote = "Administration after three hours is not advised."
    check = verify_quote(quote, CHUNK, LOOKUP)
    assert not check.passed


def test_offset_mismatch_detected():
    bad_chunk = Chunk(
        **{
            **CHUNK.__dict__,
            "char_start": 0,  # wrong offsets: canonical has PREAMBLE there
            "char_end": len(SOURCE_TEXT),
        }
    )
    check = verify_quote("three hours is not recommended.", bad_chunk, LOOKUP)
    assert check.status == QuoteStatus.FAIL_OFFSET_MISMATCH and not check.passed


def test_verify_answer_aggregates_and_flags_unknown_chunks():
    answer = (
        'Per doctrine, <quote src="CPG-03:00002">Administration\nafter three hours '
        "is not recommended.</quote> However "
        '<quote src="CPG-99:00000">invented text</quote> and '
        '<quote src="CPG-03:00002">completely fabricated quote</quote>.'
    )
    report = verify_answer(answer, {"CPG-03:00002": CHUNK}, LOOKUP)
    assert report.n_quotes == 3
    assert [c.status for c in report.checks] == [
        QuoteStatus.EXACT,
        QuoteStatus.FAIL_UNKNOWN_CHUNK,
        QuoteStatus.FAIL_NOT_FOUND,
    ]
    assert not report.integrity
    assert report.summary() == "1/3 quotes verified"


def test_answer_with_no_quotes_has_integrity():
    report = verify_answer("No verbatim claims here.", {}, None)
    assert report.integrity and report.n_quotes == 0


def test_extract_quotes_multiline():
    answer = '<quote src="A:00001">line one\nline two</quote>'
    assert extract_quotes(answer) == [("A:00001", "line one\nline two")]
