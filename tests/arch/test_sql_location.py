"""TS-ARCH-02 (T-03): the checker flags its planted control file and passes the clean src/ tree."""
import pytest

from tests.arch.checkers import CONTROLS, check_sql_location, src_files

pytestmark = pytest.mark.arch


@pytest.mark.req("NFR-22")
def test_control_is_flagged():
    found = check_sql_location([CONTROLS / "bad_sql.py.txt"], force=True)
    assert len(found) >= 2, [str(v) for v in found]


@pytest.mark.req("NFR-22")
def test_src_tree_is_clean():
    files = src_files()
    assert len(files) > 10  # the instrument actually scanned the tree
    found = check_sql_location(files)
    assert found == [], "; ".join(map(str, found))
