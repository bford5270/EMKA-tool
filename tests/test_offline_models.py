"""Model-dependent tests — skipped automatically when weights aren't staged.

The full assertion set lives in scripts/smoke.py (``make smoke``); this wrapper
lets `pytest` exercise the same path on a provisioned box without failing CI
environments that have no models.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from core.config import load_config

CFG = load_config()
MODELS_STAGED = CFG.chat_model_path.exists() and CFG.hf_cache_dir.exists()


@pytest.mark.skipif(not MODELS_STAGED, reason="model weights not staged in models/")
def test_smoke_script_passes_offline():
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/smoke.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"smoke failed:\n{result.stdout}\n{result.stderr}"
    assert "ALL PASS" in result.stdout
