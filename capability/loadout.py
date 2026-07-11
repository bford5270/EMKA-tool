"""Resource-aware inference data: the unit's actual "what's on hand" picture.

Maps to manifest rows CAP-01..CAP-07 (Capability & Formulary tab). The
manifest tracks these as governed corpus items; the DATA itself is
command-provided as simple YAML files staged under
``corpus/unit/capability/`` (unit-shelf governed, watermarked, NON-PHI):

    formulary.yaml         CAP-01  drug -> stocked, by role
    equipment.yaml         CAP-02  AMAL/ADAL equipment items
    capability_matrix.yaml CAP-03  Role 1/2/3 capability matrix
    blood_posture.yaml     CAP-04  products, units on hand, WBB status
    evac_factors.yaml      CAP-07  evacuation timeline planning factors

Every file carries ``as_of`` (ISO date) and ``source``. A stale as-of date
is a DEFECT: a wrong availability assumption is as dangerous as a wrong
clinical fact (concept paper §5). Loaders warn loudly and mark findings
``stale=True`` past EMKA_CAPABILITY_MAX_AGE_DAYS (default 120).

Templates for the command-provided files live in capability/templates/.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from core.config import EmkaConfig, load_config

ROLES = ("role1", "role2", "role3")

DEFAULT_MAX_AGE_DAYS = int(os.environ.get("EMKA_CAPABILITY_MAX_AGE_DAYS", "120"))


@dataclass(frozen=True)
class FormularyItem:
    name: str
    synonyms: tuple[str, ...]
    stocked: dict[str, bool]  # role -> stocked
    notes: str = ""


@dataclass(frozen=True)
class EquipmentItem:
    name: str
    amal: str
    roles: tuple[str, ...]
    qty: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class Dataset:
    kind: str  # formulary | equipment | capability_matrix | blood_posture | evac_factors
    as_of: date
    source: str
    stale: bool


@dataclass
class AvailabilityFinding:
    """What the generator shows next to a clinical recommendation."""

    item: str  # the term matched from the recommendation
    matched_name: str  # loadout item name it matched
    kind: str  # formulary | equipment
    available: bool | None  # None = not determinable for the given role
    role: str
    as_of: str
    source: str
    stale: bool
    notes: str = ""


class StaleCapabilityWarning(UserWarning):
    pass


def _parse_as_of(raw: object, path: Path) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except ValueError as e:
        raise ValueError(f"{path}: as_of must be an ISO date, got {raw!r}") from e


def _check_stale(kind: str, as_of: date, max_age_days: int, today: date | None = None) -> bool:
    age = ((today or date.today()) - as_of).days
    if age > max_age_days:
        import warnings

        msg = (
            f"CAPABILITY DATA STALE: {kind} as_of={as_of.isoformat()} is {age} days old "
            f"(limit {max_age_days}). A wrong availability assumption is as dangerous "
            "as a wrong clinical fact — update the command-provided file."
        )
        warnings.warn(msg, StaleCapabilityWarning, stacklevel=3)
        print(f"WARNING: {msg}", file=sys.stderr)
        return True
    return False


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


class Loadout:
    """Queryable view over all staged capability datasets."""

    def __init__(
        self,
        formulary: list[FormularyItem],
        equipment: list[EquipmentItem],
        capability_matrix: dict[str, list[str]],
        blood_posture: dict,
        evac_factors: list[dict],
        datasets: dict[str, Dataset],
    ):
        self.formulary = formulary
        self.equipment = equipment
        self.capability_matrix = capability_matrix
        self.blood_posture = blood_posture
        self.evac_factors = evac_factors
        self.datasets = datasets

    # -- matching ---------------------------------------------------------

    def match(self, recommendation: str, context: dict | None = None) -> list[AvailabilityFinding]:
        """Match a clinical recommendation's items against the loadout.

        ``recommendation`` is free text (e.g. "administer TXA 2 g IV").
        ``context`` may carry {"role": "role2"}. Returns one finding per
        loadout item whose name/synonym occurs in the recommendation. The
        CORE contract: a first-line item that is NOT stocked returns
        available=False so the generator can surface the source's own
        cited alternative — never an invented substitution.
        """
        context = context or {}
        role = str(context.get("role", "role2")).lower().replace(" ", "")
        text = f" {_norm(recommendation)} "
        findings: list[AvailabilityFinding] = []

        for item in self.formulary:
            names = (item.name, *item.synonyms)
            hit = next((n for n in names if f" {_norm(n)} " in text), None)
            if hit is None:
                continue
            ds = self.datasets["formulary"]
            findings.append(
                AvailabilityFinding(
                    item=hit,
                    matched_name=item.name,
                    kind="formulary",
                    available=item.stocked.get(role),
                    role=role,
                    as_of=ds.as_of.isoformat(),
                    source=ds.source,
                    stale=ds.stale,
                    notes=item.notes,
                )
            )
        for item in self.equipment:
            if f" {_norm(item.name)} " not in text:
                continue
            ds = self.datasets["equipment"]
            findings.append(
                AvailabilityFinding(
                    item=item.name,
                    matched_name=item.name,
                    kind="equipment",
                    available=role in item.roles,
                    role=role,
                    as_of=ds.as_of.isoformat(),
                    source=ds.source,
                    stale=ds.stale,
                    notes=item.notes,
                )
            )
        return findings

    def role_capabilities(self, role: str) -> list[str]:
        return self.capability_matrix.get(role.lower().replace(" ", ""), [])


# -- loading ----------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at top level")
    return data


def capability_dir(cfg: EmkaConfig) -> Path:
    return cfg.corpus_dir / "unit" / "capability"


def load_loadout(
    cfg: EmkaConfig | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    today: date | None = None,
) -> Loadout:
    """Load every staged dataset; missing files yield empty sections (the
    generator then reports availability as undeterminable, never guessed)."""
    cfg = cfg or load_config()
    base = capability_dir(cfg)
    datasets: dict[str, Dataset] = {}

    def dataset(kind: str, filename: str) -> dict | None:
        path = base / filename
        if not path.exists():
            return None
        data = _load_yaml(path)
        as_of = _parse_as_of(data.get("as_of"), path)
        stale = _check_stale(kind, as_of, max_age_days, today)
        datasets[kind] = Dataset(
            kind=kind, as_of=as_of, source=str(data.get("source", "unspecified")), stale=stale
        )
        return data

    formulary: list[FormularyItem] = []
    data = dataset("formulary", "formulary.yaml")
    if data:
        for row in data.get("items", []):
            stocked = {str(k).lower(): bool(v) for k, v in (row.get("stocked") or {}).items()}
            formulary.append(
                FormularyItem(
                    name=str(row["name"]),
                    synonyms=tuple(str(s) for s in row.get("synonyms", [])),
                    stocked=stocked,
                    notes=str(row.get("notes", "")),
                )
            )

    equipment: list[EquipmentItem] = []
    data = dataset("equipment", "equipment.yaml")
    if data:
        for row in data.get("items", []):
            equipment.append(
                EquipmentItem(
                    name=str(row["name"]),
                    amal=str(row.get("amal", "")),
                    roles=tuple(str(r).lower() for r in row.get("roles", [])),
                    qty=row.get("qty"),
                    notes=str(row.get("notes", "")),
                )
            )

    matrix: dict[str, list[str]] = {}
    data = dataset("capability_matrix", "capability_matrix.yaml")
    if data:
        for role, caps in (data.get("roles") or {}).items():
            matrix[str(role).lower().replace(" ", "")] = [str(c) for c in caps or []]

    blood = dataset("blood_posture", "blood_posture.yaml") or {}
    evac_data = dataset("evac_factors", "evac_factors.yaml") or {}
    evac = [dict(f) for f in evac_data.get("factors", [])]

    return Loadout(formulary, equipment, matrix, blood, evac, datasets)
