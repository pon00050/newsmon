"""DisplayPolicy and LicenceGate (T-22 essential portion): FR-06, FR-27(d), FR-31(b)."""
import pytest

from newsmon.domain.models import LicenceFlags
from newsmon.licence.policy import DisplayPolicy, LicenceGate

pytestmark = pytest.mark.unit
SUMMARY = "This feed summary must never appear for a headline-only source."


def art(flags: LicenceFlags, restrictions=None, url="https://example.com/a"):
    return {"uid": "a1", "licence_snapshot": flags.snapshot_json(), "restrictions": restrictions, "headline": "H",
            "description_text": SUMMARY, "body_text": "Body text.", "canonical_url": url}


@pytest.mark.req("FR-06c", "RA-10")
def test_headline_only_hides_summary_and_body():
    v = DisplayPolicy.render(art(LicenceFlags(display="headline")))
    assert v["headline"] == "H" and v["summary"] is None and v["body"] is None


@pytest.mark.req("RA-10")
def test_levels():
    assert DisplayPolicy.render(art(LicenceFlags(display="none")))["headline"] is None
    snip = DisplayPolicy.render(art(LicenceFlags(display="snippet")))
    assert snip["summary"] == SUMMARY and snip["body"] is None
    full = DisplayPolicy.render(art(LicenceFlags(display="full", storage="full")))
    assert full["summary"] == SUMMARY and full["body"] == "Body text."


@pytest.mark.req("FR-31b")
def test_unknown_restriction_caps_at_headline():
    v = DisplayPolicy.render(art(LicenceFlags(display="full", storage="full"), restrictions="ZZ-UNKNOWN-RESTRICTION"))
    assert v["display"] == "headline" and v["summary"] is None and v["body"] is None and v["restricted"]


@pytest.mark.req("FR-27d")
def test_synthetic_is_provenance_only():
    for display in ("headline", "full"):
        a = DisplayPolicy.render(art(LicenceFlags(display=display, synthetic=False)))
        b = DisplayPolicy.render(art(LicenceFlags(display=display, synthetic=True)))
        assert {k: v for k, v in a.items()} == {k: v for k, v in b.items()}
    assert LicenceGate.storage(LicenceFlags(storage="metadata", synthetic=True)) == \
        LicenceGate.storage(LicenceFlags(storage="metadata"))


@pytest.mark.req("FR-06a", "FR-06b")
def test_storage_gate():
    assert not LicenceGate.storage(LicenceFlags(storage="metadata")).keep_body
    assert not LicenceGate.may_fetch_body(LicenceFlags(storage="metadata"))
    t = LicenceGate.storage(LicenceFlags(storage="transient"))
    assert t.use_body_for_features and not t.keep_body
    assert LicenceGate.storage(LicenceFlags(storage="full")).keep_body
    assert not LicenceGate.storage(LicenceFlags(storage="none")).store


def test_only_http_links():
    assert DisplayPolicy.render(art(LicenceFlags(), url="javascript:alert(1)"))["link"] is None
