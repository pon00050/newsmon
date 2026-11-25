"""TS-ARCH-05 (T-03): the checker flags its planted control file and passes the clean src/ tree."""
import pytest

from tests.arch.checkers import CONTROLS, check_no_training, src_files

pytestmark = pytest.mark.arch


@pytest.mark.req("NFR-19")
def test_control_is_flagged():
    found = check_no_training([CONTROLS / "bad_training.py.txt"], force=True)
    assert len(found) >= 3, [str(v) for v in found]


@pytest.mark.req("NFR-19")
def test_src_tree_is_clean():
    files = src_files()
    assert len(files) > 10  # the instrument actually scanned the tree
    found = check_no_training(files)
    assert found == [], "; ".join(map(str, found))
