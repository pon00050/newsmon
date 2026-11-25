"""Public publication gate and static export (website dashboard).

Controls: a source without a public permission must contribute nothing; summary and body text (planted canaries) must
never reach the public file; restricted, withheld, embargoed and withdrawn items are refused; the validator rejects any
field outside the contract.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from newsmon.cli import main as cli_main
from newsmon.publish import export
from newsmon.publish.gate import decide, public_record
from newsmon.registry.loader import SourceSpec, parse_sources
from newsmon.config.loader import ConfigError
from tests.support.fixture_server import Resp
from tests.support.instance import feed_source, make_app

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
BASIS = {"public_redistribution": "headline", "public_redistribution_basis": "US federal work (17 U.S.C. 105)"}
CANARY_DESC = "CANARYDESCRIPTIONXQ"
CANARY_TITLE = "Public canary headline"


def _spec(**kw) -> SourceSpec:
    d = {"key": "s", "name": "S", "access_method": "feed", "url": "https://example.org/rss", **BASIS}
    d.update(kw)
    return SourceSpec.model_validate(d)


def _row(**kw) -> dict:
    snap = json.dumps({"storage": "metadata", "display": "headline"})
    d = {"uid": "a_1", "source_key": "s", "source_name": "S", "lang": "en", "published_utc": None,
         "first_seen_utc": "2026-11-25T11:00:00+00:00", "headline": "H", "canonical_url": "https://example.org/a",
         "final_band": "review", "rule_score": 1.0, "status": "live", "pubstatus": "usable", "embargoed_utc": None,
         "restrictions": None, "licence_snapshot": snap, "synthetic": 0, "dup_count": 0,
         "rule_ids": ["topic:Trade", "entity:china", "recency"]}
    d.update(kw)
    return d


# --- the gate ------------------------------------------------------------------------------------------------------------
def test_default_is_deny():
    assert decide(_row(), _spec(public_redistribution="none", public_redistribution_basis=None), NOW).level == "none"
    assert decide(_row(), None, NOW).level == "none"
    assert decide(_row(), _spec(), NOW).level == "headline"


def test_permission_needs_a_written_basis_and_never_covers_customer_content():
    with pytest.raises(ConfigError):
        parse_sources({"sources": [{"key": "s", "name": "S", "access_method": "feed", "url": "https://e.org/r",
                                    "public_redistribution": "headline"}]})
    with pytest.raises(ConfigError):
        parse_sources({"sources": [{"key": "s", "name": "S", "access_method": "feed", "url": "https://e.org/r",
                                    "licence_owner": "tenant", **BASIS}]})


@pytest.mark.parametrize("change, reason", [
    ({"restrictions": "No access Japan"}, "restriction"),
    ({"status": "withdrawn"}, "withdrawn"),
    ({"status": "gone"}, "gone"),
    ({"pubstatus": "withheld"}, "withheld"),
    ({"embargoed_utc": "2026-11-26T00:00:00+00:00"}, "embargoed"),
    ({"embargoed_utc": "not a date"}, "embargoed"),
    ({"canonical_url": "javascript:alert(1)"}, "link"),
    ({"canonical_url": None}, "link"),
    ({"licence_snapshot": json.dumps({"storage": "metadata", "display": "none"})}, "displayable"),
    ({"licence_snapshot": json.dumps({"licence_owner": "tenant"})}, "customer"),
    ({"licence_snapshot": "{not json"}, "unreadable"),
])
def test_internal_restrictions_still_apply(change, reason):
    d = decide(_row(**change), _spec(), NOW)
    assert d.level == "none" and reason in d.reason


def test_passed_embargo_and_linkless_synthetic_are_allowed():
    assert decide(_row(embargoed_utc="2026-11-24T00:00:00+00:00"), _spec(), NOW).level == "headline"
    assert decide(_row(canonical_url=None, synthetic=1), _spec(), NOW).level == "headline"


def test_record_is_the_closed_field_list():
    rec = public_record(_row(description_text="secret", body_text="secret"), "metadata")
    assert set(rec) == export.ITEM_KEYS and rec["headline"] is None
    assert rec["topics"] == ["Trade"] and rec["entities"] == ["china"]
    assert "secret" not in json.dumps(rec)


# --- the validator -------------------------------------------------------------------------------------------------------
def _doc(items=None, level="headline", dataset="live") -> dict:
    items = items if items is not None else [public_record(_row(), level)]
    return {"schema": export.SCHEMA, "dataset": dataset, "generated_utc": NOW.isoformat(), "newsmon_version": "0.1.0",
            "profile": {"key": "p", "name": "P"}, "notice": "n", "stats": export.stats(items), "items": items,
            "sources": [{"key": "s", "name": "S", "public_level": level, "basis": "b", "basis_url": None,
                         "attribution": None, "items": len(items), "last_success_utc": None, "last_status": "ok"}]}


def test_validator_accepts_contract_and_rejects_leaks():
    export.validate(_doc())
    bad = _doc()
    bad["items"][0]["summary"] = "text"
    with pytest.raises(export.PublicExportError):
        export.validate(bad)
    bad = _doc()
    bad["items"][0]["link"] = "javascript:alert(1)"
    with pytest.raises(export.PublicExportError):
        export.validate(bad)
    with pytest.raises(export.PublicExportError):  # headline from a metadata-only source
        export.validate(_doc(items=[public_record(_row(), "headline")], level="metadata"))
    with pytest.raises(export.PublicExportError):  # real items in the synthetic dataset
        export.validate(_doc(dataset="synthetic"))
    bad = _doc()
    bad["debug"] = {}
    with pytest.raises(export.PublicExportError):
        export.validate(bad)


def test_rolling_snapshot_is_bounded_and_rechecked():
    new = _doc(items=[public_record(_row(uid="a_new", first_seen_utc="2026-11-25T11:00:00+00:00"), "headline")])
    prev = _doc(items=[public_record(_row(uid=f"a_{i}", first_seen_utc=(NOW - timedelta(days=i)).isoformat()), "headline")
                       for i in range(1, 30)])
    prev["items"].append(dict(prev["items"][0], uid="a_gone_source", source_key="revoked"))
    out = export.merge_previous(new, prev, max_items=10, max_age_days=14)
    uids = [i["uid"] for i in out["items"]]
    assert len(uids) == 10 and uids[0] == "a_new" and "a_gone_source" not in uids
    out = export.merge_previous(new, prev, max_items=50, max_age_days=14, exclude_uids={"a_1", "a_2"})
    assert "a_1" not in [i["uid"] for i in out["items"]] and "a_3" in [i["uid"] for i in out["items"]]  # refused now
    out = export.merge_previous(_doc(items=[], level="metadata"), prev, max_items=50, max_age_days=14)
    assert out["items"] and all(i["headline"] is None for i in out["items"])  # downgraded permission applies backwards
    assert all(datetime.fromisoformat(i["first_seen_utc"]) >= NOW - timedelta(days=14) for i in out["items"])


# --- end to end through the real pipeline --------------------------------------------------------------------------------
TEXTS = {"pub": "Officials announced a review of port inspection rules after a week of delays at the harbour.",
         "priv": "A regional orchestra will tour four cities in spring with a programme of new commissions.",
         "meta": "Engineers completed the third test flight of a small weather satellite ahead of schedule."}


def _rss(items: list[tuple[str, str]], text: str) -> bytes:
    # distinct texts: near-duplicates would be collapsed onto one primary and hide the other sources
    body = "".join(f"<item><title>{t}</title><link>{link}</link><guid>{link}</guid>"
                   f"<description>{CANARY_DESC} {text}</description>"
                   f"<pubDate>Wed, 25 Nov 2026 10:00:00 GMT</pubDate></item>" for t, link in items)
    return f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>t</title>{body}</channel></rss>'.encode()


def test_export_publishes_only_permitted_sources_and_never_text(tmp_path, fixture_server):
    fixture_server.route("/robots.txt", Resp(body=b"User-agent: *\nAllow: /\n", content_type="text/plain"))
    pub = fixture_server.route("/pub.xml", Resp(body=_rss([(CANARY_TITLE, "https://example.org/p1")], TEXTS["pub"])))
    priv = fixture_server.route("/priv.xml", Resp(body=_rss([("Private item headline", "https://example.org/q1")], TEXTS["priv"])))
    meta = fixture_server.route("/meta.xml", Resp(body=_rss([("Metadata only headline", "https://example.org/m1")], TEXTS["meta"])))
    sources = [feed_source("pub", pub, storage="full", display="full", **BASIS),
               feed_source("priv", priv, storage="full", display="full"),
               feed_source("meta", meta, public_redistribution="metadata",
                           public_redistribution_basis="documented in test")]
    app = make_app(tmp_path, fixture_server, sources)
    try:
        app.collect(force=True)
        doc = export.build(app, "live")
    finally:
        app.close()
    refused = doc.pop("_refused")
    assert refused == {"public redistribution not permitted for this source": 1}  # the priv item
    out = export.write(doc, tmp_path / "live.json")
    text = out.read_text(encoding="utf-8")
    items = json.loads(text)["items"]
    assert {i["source_key"] for i in items} == {"pub", "meta"}
    assert CANARY_TITLE in text and "Private item headline" not in text and "Metadata only headline" not in text
    assert CANARY_DESC not in text  # descriptions are stored (storage=full) but never published


def test_synthetic_demo_build_end_to_end(tmp_path):
    """The website's synthetic dataset: demo config + generated inbox -> init -> collect -> export-public."""
    cfg, data = tmp_path / "config", tmp_path / "data"
    shutil.copytree(ROOT / "demo" / "config", cfg)
    inbox = cfg / "inbox" / "demo"
    inbox.mkdir(parents=True)
    subprocess.run([sys.executable, "-I", str(ROOT / "demo" / "make_demo_inbox.py"), "--out", str(inbox)],
                   check=True, capture_output=True)
    common = ["--config", str(cfg), "--data", str(data)]
    assert cli_main(["init", *common]) == 0
    assert cli_main(["collect", "--force", *common]) == 0
    assert cli_main(["collect", "--force", *common]) == 0  # two-scan stability rule
    out = tmp_path / "synthetic.json"
    assert cli_main(["export-public", "--dataset", "synthetic", "--out", str(out), *common]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    export.validate(doc)
    assert doc["stats"]["items"] >= 30 and all(i["synthetic"] for i in doc["items"])
    assert len({b for b, n in doc["stats"]["by_band"].items() if n}) >= 3  # ranking produced a spread of bands
    assert "[SYNTHETIC DEMO]" not in out.read_text(encoding="utf-8")  # the marker lives only in bodies
    # the same data cannot be exported as live
    assert cli_main(["export-public", "--dataset", "live", "--out", str(tmp_path / "x.json"), *common]) == 0
    assert json.loads((tmp_path / "x.json").read_text(encoding="utf-8"))["items"] == []
