"""TS-HAR-05 (T-04): req_coverage.py exits non-zero when an id is missing (control) and zero when complete."""
import pytest

from tools.req_coverage import main

pytestmark = pytest.mark.support

JUNIT = """<?xml version="1.0"?><testsuites><testsuite name="pytest">
<testcase classname="t" name="a"><properties><property name="req" value="FR-01a"/></properties></testcase>
<testcase classname="t" name="b"><properties><property name="req" value="FR-01b"/></properties>{b_outcome}</testcase>
<testcase classname="t" name="c"><properties><property name="req" value="FR-01c"/></properties><skipped/></testcase>
</testsuite></testsuites>"""


def _write(tmp_path, b_outcome=""):
    p = tmp_path / "junit.xml"
    p.write_text(JUNIT.format(b_outcome=b_outcome), encoding="utf-8")
    return p


def test_complete_report_passes(tmp_path):
    assert main([str(_write(tmp_path)), "--ids", "FR-01a,FR-01b"]) == 0


def test_missing_id_fails(tmp_path, capsys):
    assert main([str(_write(tmp_path)), "--ids", "FR-01a,FR-99z"]) == 1
    assert "MISSING FR-99z" in capsys.readouterr().out


def test_skipped_and_failed_do_not_count(tmp_path):
    assert main([str(_write(tmp_path)), "--ids", "FR-01c"]) == 1
    assert main([str(_write(tmp_path, '<failure message="x"/>')), "--ids", "FR-01b"]) == 1


def test_groups_file(tmp_path):
    ids = tmp_path / "ids.txt"
    ids.write_text("FR-01a\to1\t\nFR-01b\to1,release_a\t\n", encoding="utf-8")
    assert main([str(_write(tmp_path)), "--require", "release_a", "--ids-file", str(ids)]) == 0
    assert main([str(_write(tmp_path)), "--require", "nope", "--ids-file", str(ids)]) == 2
