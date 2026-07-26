"""Capability loader tests. Core contract: first-line item absent ->
available=False so a cited alternative can be surfaced (never invented)."""

from __future__ import annotations

import shutil
import warnings
from datetime import date
from pathlib import Path

import pytest

from capability.loadout import (
    DEFAULT_MAX_AGE_DAYS,
    StaleCapabilityWarning,
    load_loadout,
)
from core.config import load_config

TEMPLATES = Path(__file__).resolve().parent.parent / "capability" / "templates"


@pytest.fixture()
def staged(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    cap = corpus / "unit" / "capability"
    cap.mkdir(parents=True)
    for f in TEMPLATES.glob("*.yaml"):
        shutil.copy(f, cap / f.name)
    monkeypatch.setenv("EMKA_CORPUS_DIR", str(corpus))
    return load_config()


def test_loads_all_datasets(staged):
    lo = load_loadout(staged, today=date(2026, 7, 11))
    assert {d for d in lo.datasets} == {
        "formulary",
        "equipment",
        "capability_matrix",
        "blood_posture",
        "evac_factors",
    }
    assert all(not d.stale for d in lo.datasets.values())
    assert lo.blood_posture["walking_blood_bank"]["screened_donors"] == 40
    assert lo.evac_factors[0]["timeline_hours"] == 2


def test_first_line_absent_returns_available_false(staged):
    """THE core case: ertapenem is first-line but not stocked at Role 2."""
    lo = load_loadout(staged, today=date(2026, 7, 11))
    findings = lo.match(
        "Administer ertapenem 1 g IV q24h for intra-abdominal infection",
        {"role": "role2"},
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.matched_name == "ertapenem"
    assert f.available is False
    assert f.as_of == "2026-07-01" and not f.stale


def test_synonym_matching_and_role_awareness(staged):
    lo = load_loadout(staged, today=date(2026, 7, 11))
    # TXA via synonym, stocked at role1
    f = lo.match("give TXA 2 g IV slow push", {"role": "role1"})
    assert f and f[0].matched_name == "tranexamic acid" and f[0].available is True
    # FDP absent at role1, present at role2
    assert lo.match("infuse FDP", {"role": "role1"})[0].available is False
    assert lo.match("infuse FDP", {"role": "role2"})[0].available is True


def test_equipment_matching(staged):
    lo = load_loadout(staged, today=date(2026, 7, 11))
    f = lo.match("initiate mechanical ventilation with portable ventilator", {"role": "role1"})
    assert f and f[0].kind == "equipment" and f[0].available is False
    assert lo.match("portable ventilator setup", {"role": "role2"})[0].available is True


def test_unknown_item_yields_no_finding(staged):
    lo = load_loadout(staged, today=date(2026, 7, 11))
    assert lo.match("administer unicorn dust", {"role": "role2"}) == []


def test_role_capability_matrix(staged):
    lo = load_loadout(staged, today=date(2026, 7, 11))
    assert "damage control resuscitation" in lo.role_capabilities("role2")
    assert "damage control resuscitation" not in lo.role_capabilities("role1")


def test_stale_as_of_warns_loudly_and_marks_findings(staged, capsys):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        lo = load_loadout(staged, today=date(2027, 7, 11))  # a year later
    assert any(issubclass(w.category, StaleCapabilityWarning) for w in caught)
    assert "CAPABILITY DATA STALE" in capsys.readouterr().err
    f = lo.match("give TXA", {"role": "role2"})
    assert f[0].stale is True


def test_missing_files_yield_empty_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("EMKA_CORPUS_DIR", str(tmp_path / "empty-corpus"))
    lo = load_loadout(load_config())
    assert lo.formulary == [] and lo.equipment == []
    assert lo.match("give TXA", {"role": "role2"}) == []


def test_default_max_age_configured():
    assert DEFAULT_MAX_AGE_DAYS == 120
