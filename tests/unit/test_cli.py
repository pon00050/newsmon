"""TS-U-cli (T-01)."""
import subprocess
import sys

import pytest

from newsmon import __version__
from newsmon.cli import main

pytestmark = pytest.mark.unit


def test_version_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"newsmon {__version__}"


def test_version_matches_installed_metadata():
    assert __version__ == "0.1.0"


def test_unknown_subcommand_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["no-such-command"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_console_script_entry_point():
    out = subprocess.run([sys.executable, "-m", "newsmon.cli", "--version"], capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip() == f"newsmon {__version__}"
