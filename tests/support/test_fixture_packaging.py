"""TS-FIX-02 (T-05): corpus-derived fixtures are private research data and never ship in the wheel.

Builds the wheel offline into tmp_path (no network); skips only if the build backend is not cached.
"""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.support

ROOT = Path(__file__).resolve().parents[2]


def test_wheel_excludes_fixtures(tmp_path):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH")
    proc = subprocess.run([uv, "build", "--wheel", "--offline", "--out-dir", str(tmp_path)],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0:
        pytest.skip(f"offline wheel build unavailable (build backend not cached?):\n{proc.stderr}")
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, wheels
    with zipfile.ZipFile(wheels[0]) as zf:
        names = zf.namelist()
    leaked = [n for n in names if "tests/" in n or "fixtures" in n]
    assert leaked == [], leaked
    assert "newsmon/cli.py" in names
