"""TS-ARCH-07 (T-03): the checker flags its planted control file and passes the clean src/ tree."""
import pytest

from tests.arch.checkers import CONTROLS, check_forbidden_imports, src_files

pytestmark = pytest.mark.arch


def test_control_is_flagged():
    found = check_forbidden_imports([CONTROLS / "bad_browser.py.txt"], force=True)
    assert len(found) >= 4, [str(v) for v in found]


def test_src_tree_is_clean():
    files = src_files()
    assert len(files) > 10  # the instrument actually scanned the tree
    found = check_forbidden_imports(files)
    assert found == [], "; ".join(map(str, found))
