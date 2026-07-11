"""Scaffold sanity: every package imports and the repo contract files exist."""

import importlib
from pathlib import Path

import pytest

PACKAGES = ["core", "ingest", "retrieval", "generate", "capability", "api", "eval"]


@pytest.mark.parametrize("pkg", PACKAGES)
def test_package_imports(pkg):
    importlib.import_module(pkg)


def test_contract_files_exist():
    root = Path(__file__).resolve().parent.parent
    for f in ["DESIGN.md", "Makefile", "pyproject.toml", "docs/EMKA_Corpus_Manifest.xlsx"]:
        assert (root / f).exists(), f"missing {f}"
