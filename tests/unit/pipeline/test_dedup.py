"""Near-duplicate signatures (T-20): FR-08(a) recall >= 0.95 on R6's labelled pairs with exact Jaccard >= 0.5."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from newsmon.pipeline import dedup
from newsmon.pipeline.normalise import fold

pytestmark = pytest.mark.unit
GOLD = Path(__file__).resolve().parents[2] / "fixtures" / "gold"
T0 = datetime(2026, 11, 25, tzinfo=timezone.utc)


@pytest.mark.req("FR-08a", "NFR-11")
def test_recall_on_r6_pairs():
    pairs = json.loads((GOLD / "dedup_pairs.json").read_text(encoding="utf-8"))
    assert len(pairs) == 36
    eligible = [p for p in pairs if dedup.exact_jaccard(fold(p["a"]["text"]), fold(p["b"]["text"])) >= 0.5]
    assert eligible, "instrument control: some pairs must be eligible"
    found = 0
    for p in eligible:
        idx = dedup.NearDupIndex()
        idx.add(dedup.Candidate(1, 1, 1, T0, None, False), dedup.signature(fold(p["a"]["text"])))
        links = idx.links_for(dedup.signature(fold(p["b"]["text"])), source_id=2, first_seen=T0, story_key=None,
                              is_live=False)
        found += bool(links)
    recall = found / len(eligible)
    print(f"FR-08a: {found}/{len(eligible)} eligible pairs linked (recall {recall:.3f})")
    assert recall >= 0.95


def test_nonsense_pair_not_linked():
    idx = dedup.NearDupIndex()
    idx.add(dedup.Candidate(1, 1, 1, T0, None, False), dedup.signature("the cat sat on the mat in the sun"))
    assert idx.links_for(dedup.signature("stock markets fell sharply in tokyo today"), source_id=2, first_seen=T0,
                         story_key=None, is_live=False) == []


def test_classification_rules():
    assert dedup.classify(0.95, same_source=True, within_window=False) == "same_item"
    assert dedup.classify(0.6, same_source=False, within_window=False) == "syndicated"
    assert dedup.classify(0.6, same_source=True, within_window=True) == "revision"
    assert dedup.classify(0.6, same_source=True, within_window=False) is None
    assert dedup.classify(0.3, same_source=False, within_window=True) is None


def test_live_items_never_linked():
    idx = dedup.NearDupIndex()
    sig = dedup.signature("live updates: the war continues with many shared words of boilerplate text")
    idx.add(dedup.Candidate(1, 1, 1, T0, None, True), sig)
    assert idx.links_for(sig, source_id=1, first_seen=T0, story_key=None, is_live=False) == []
    idx.add(dedup.Candidate(2, 2, 1, T0, None, False), sig)
    assert idx.links_for(sig, source_id=1, first_seen=T0, story_key=None, is_live=True) == []


def test_story_key_revision_within_48h():
    idx = dedup.NearDupIndex()
    idx.add(dedup.Candidate(1, 1, 7, T0, "k", False), dedup.signature("completely different words here"))
    got = idx.links_for(dedup.signature("nothing in common at all zzz"), source_id=7, first_seen=T0 + timedelta(hours=3),
                        story_key="k", is_live=False)
    assert [link.kind for link in got] == ["revision"]
    late = idx.links_for(dedup.signature("nothing in common at all zzz"), source_id=7, first_seen=T0 + timedelta(hours=60),
                         story_key="k", is_live=False)
    assert late == []


def test_blob_roundtrip():
    s = dedup.signature("abc def ghi")
    assert dedup.from_blob(dedup.to_blob(s)).jaccard(s) == 1.0
