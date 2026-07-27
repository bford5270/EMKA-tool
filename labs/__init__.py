"""EMKA labs — deterministic lab-value interpretation (IDC Lab Assistant).

Vendored from bford5270/idc-lab-assistant @ ed8a97f. A rules-based engine:
guideline-anchored thresholds in ``rules.json`` classify a lab value's
severity and return paste-ready EHR/patient language, plus panel-level
derived computations (eGFR/CKD-EPI 2021, KDIGO AKI staging, anion gap,
BUN/Cr, AHA PREVENT). It NEVER guesses a threshold — the same "cite, don't
invent" discipline EMKA applies to doctrine (DESIGN.md §7, §12).

PHI: this module processes patient lab VALUES. Per DESIGN.md §1 (revised),
lab values are handled strictly in memory and are NEVER persisted — the API
layer must not log them. Callers own that invariant.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from labs.engine import evaluate, evaluate_panel, evaluate_qualitative
from labs.engine import load_rules as _load_rules
from labs.lab_parser import ParsedLab, parse_text

RULES_PATH = Path(__file__).resolve().parent / "rules.json"

__all__ = [
    "RULES_PATH",
    "ParsedLab",
    "evaluate",
    "evaluate_panel",
    "evaluate_qualitative",
    "load_rules",
    "parse_text",
]


@lru_cache(maxsize=1)
def load_rules(path: str | Path | None = None) -> dict:
    """Load the packaged lab rules (or an override path). Cached — the rules
    file is static at runtime, like the corpus is between refreshes."""
    return _load_rules(path or RULES_PATH)
