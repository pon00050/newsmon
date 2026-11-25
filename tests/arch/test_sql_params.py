"""TS-ARCH-06 (T-03): the checker flags its planted control file and passes the clean src/ tree."""
import pytest

from tests.arch.checkers import CONTROLS, check_sql_params, src_files

pytestmark = pytest.mark.arch


def test_control_is_flagged():
    found = check_sql_params([CONTROLS / "bad_sql_params.py.txt"], force=True)
    assert len(found) >= 3, [str(v) for v in found]


def test_src_tree_is_clean():
    files = src_files()
    assert len(files) > 10  # the instrument actually scanned the tree
    found = check_sql_params(files)
    assert found == [], "; ".join(map(str, found))


def test_vetted_helpers_are_not_flagged():
    assert check_sql_params([CONTROLS / "good_sql_params.py.txt"], force=True) == []
