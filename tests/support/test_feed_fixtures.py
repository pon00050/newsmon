"""TS-FIX-01 (T-05): the recorded feed fixtures and phase-1 gold sets exist, parse, and have their recorded sizes.

Fixtures are built by tools/build_fixtures.py (stdlib only; `--check` proves they are current).
Feeds are parsed from BYTES read off disk; nothing here opens a URL or a socket.
"""
from __future__ import annotations

import json
from pathlib import Path

import feedparser
import numpy as np
import pytest

pytestmark = pytest.mark.support

ROOT = Path(__file__).resolve().parents[2]
FEEDS = ROOT / "tests" / "fixtures" / "feeds"
GOLD = ROOT / "tests" / "fixtures" / "gold"
NOT_PARSED_HERE = {"malformed.xml", "xxe_rss.xml"}  # xxe_rss.xml is parsed only by the hardened path (T-15)


def _manifest() -> dict:
    return json.loads((FEEDS / "MANIFEST.json").read_text(encoding="utf-8"))


def _parse(name: str):
    return feedparser.parse((FEEDS / name).read_bytes())


def _gold(name: str):
    return json.loads((GOLD / name).read_text(encoding="utf-8"))


def _good_feed_files() -> list[str]:
    return sorted(p.name for p in FEEDS.glob("*.xml") if p.name not in NOT_PARSED_HERE)


def _find(entries, *, guid=None, link=None):
    hits = []
    for e in entries:
        if guid is not None and e.get("id") == guid:
            hits.append(e)
        elif link is not None and (e.get("link") == link or any(lk.get("href") == link for lk in e.get("links", []))):
            hits.append(e)
    assert len(hits) == 1, f"expected exactly one entry for guid={guid!r} link={link!r}, found {len(hits)}"
    return hits[0]


# --------------------------------------------------------------------------- feeds

@pytest.mark.parametrize("name", _good_feed_files())
def test_good_feed_parses_without_bozo(name):
    parsed = _parse(name)
    assert not parsed.bozo, f"{name}: {parsed.get('bozo_exception')!r}"
    meta = _manifest()["files"][name]
    assert parsed.version.startswith(meta["format"]), (name, parsed.version)
    assert len(parsed.entries) == meta["items"]
    if name != "empty.xml":
        assert 5 <= len(parsed.entries) <= 20, name
        assert parsed.feed.get("title"), name


def test_malformed_feed_is_bozo():
    assert _parse("malformed.xml").bozo


def test_every_feed_file_is_listed_in_manifest_and_small():
    files = _manifest()["files"]
    on_disk = sorted(p.name for p in FEEDS.glob("*.xml"))
    assert on_disk == sorted(files)
    for name in on_disk:
        assert (FEEDS / name).stat().st_size < 200_000, name


def test_at_least_ten_normal_feeds_in_all_three_languages():
    files = _manifest()["files"]
    normal = {n: m for n, m in files.items() if m["expect"] == "ok" and m["items"] > 0}
    assert len(normal) >= 10
    assert {m["lang"] for m in normal.values()} == {"en", "ko", "zh"}
    assert sum(m["format"] == "atom" for m in normal.values()) >= 2
    for lang in ("en", "ko", "zh"):
        assert any(m["lang"] == lang for m in normal.values())


def test_manifest_lists_every_edge_case():
    assert set(_manifest()["edge_cases"]) == {
        "missing_pubdate", "tracking_url", "empty_title", "html_in_summary", "guardian_liveblog_pair",
        "yonhap_jonghap_pair", "iheart_copies", "external_entity", "malformed", "empty_feed", "cross_format_story",
    }


def test_edge_missing_pubdate():
    c = _manifest()["edge_cases"]["missing_pubdate"]
    e = _find(_parse(c["file"]).entries, guid=c["guid"])
    assert "published" not in e and "published_parsed" not in e


def test_edge_tracking_url():
    c = _manifest()["edge_cases"]["tracking_url"]
    e = _find(_parse(c["file"]).entries, link=c["link"])
    assert e.link == "https://www.bbc.com/news/articles/abc123?at_medium=RSS&at_campaign=rss#frag"
    assert c["canonical"] == "https://www.bbc.com/news/articles/abc123"


def test_edge_empty_title():
    c = _manifest()["edge_cases"]["empty_title"]
    e = _find(_parse(c["file"]).entries, guid=c["guid"])
    assert e.get("title", "") == ""
    assert b"<title></title>" in (FEEDS / c["file"]).read_bytes()


def test_edge_html_in_summary():
    c = _manifest()["edge_cases"]["html_in_summary"]
    _find(_parse(c["file"]).entries, guid=c["guid"])
    raw = (FEEDS / c["file"]).read_bytes().decode("utf-8")
    for frag in ("&lt;script&gt;alert(1)&lt;/script&gt;", "&lt;img src=x onerror=alert(1)&gt;",
                 "&lt;a href=&quot;javascript:alert(1)&quot;&gt;x&lt;/a&gt;"):
        assert frag in raw, frag


def test_edge_guardian_liveblog_pair():
    c = _manifest()["edge_cases"]["guardian_liveblog_pair"]
    entries = _parse(c["file"]).entries
    a, b = (_find(entries, guid=g) for g in c["guids"])
    assert a.title.startswith("Russia-Ukraine war live:") and b.title.startswith("Russia-Ukraine war live:")
    assert a.title != b.title and a.link != b.link
    wa, wb = a.summary.split(), b.summary.split()
    shared_prefix = next(i for i, (x, y) in enumerate(zip(wa, wb)) if x != y)
    assert shared_prefix >= 50  # long shared boilerplate
    assert c["same_story"] is False


def test_edge_yonhap_jonghap_pair():
    c = _manifest()["edge_cases"]["yonhap_jonghap_pair"]
    entries = _parse(c["file"]).entries
    a, b = (_find(entries, guid=g) for g in c["guids"])
    assert {a.title, b.title} == {"북한, 동해상으로 탄도미사일 발사", "북한, 동해상으로 탄도미사일 발사(종합)"}
    assert a.link != b.link
    assert c["same_story"] is True


def test_edge_iheart_copies():
    c = _manifest()["edge_cases"]["iheart_copies"]
    entries = _parse(c["file"]).entries
    found = [_find(entries, link=lk) for lk in c["links"]]
    assert len(found) == 12
    hosts = [lk.split("/")[2] for lk in c["links"]]
    iheart = [h for h in hosts if h.endswith(".iheart.com")]
    assert len(iheart) == 10 and len(set(iheart)) == 10
    others = sorted(h.removeprefix("www.") for h in hosts if not h.endswith(".iheart.com"))
    assert others == ["apnews.com", "freemalaysiatoday.com"]
    assert c["expected_independent_sources"] == 3


def test_edge_external_entity_declared_not_parsed():
    c = _manifest()["edge_cases"]["external_entity"]
    raw = (FEEDS / c["file"]).read_bytes()
    assert b'<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>' in raw
    assert b"&xxe;" in raw


def test_edge_empty_feed():
    c = _manifest()["edge_cases"]["empty_feed"]
    parsed = _parse(c["file"])
    assert not parsed.bozo and parsed.entries == [] and parsed.feed.get("title")


def test_edge_malformed_named():
    assert _manifest()["edge_cases"]["malformed"]["file"] == "malformed.xml"


def test_edge_cross_format_story():
    c = _manifest()["edge_cases"]["cross_format_story"]
    e = _find(_parse(c["file"]).entries, guid="https://news.example.com/world/un-sudan-session")
    assert e.link == "https://news.example.com/world/un-sudan-session"
    assert e.title == "UN Security Council schedules emergency session on Sudan ceasefire"
    assert e.summary == (
        "The UN Security Council will hold an emergency session on Thursday to discuss the collapsing ceasefire in "
        "Sudan, diplomats said, after renewed fighting around El Fasher killed dozens of civilians.")


# --------------------------------------------------------------------------- gold sets

def test_gold_dedup_pairs_36():
    pairs = _gold("dedup_pairs.json")
    assert len(pairs) == 36
    assert sum(p["set"] == "title+summary" for p in pairs) == 32
    assert sum(p["set"] == "full_text" for p in pairs) == 4
    for p in pairs:
        assert set(p) == {"set", "band", "jaccard", "cross_source", "a", "b"}
        assert set(p["a"]) == set(p["b"]) == {"src", "lang", "url", "text"}


def test_gold_cluster_240():
    items = _gold("cluster_gold_240.json")
    assert len(items) == 240
    assert len({i["gid"] for i in items}) == 240
    for i in items:
        assert set(i) == {"gid", "item_id", "lang", "source", "published", "title", "summary", "label"}
        assert i["label"]
    by_gid = {i["gid"]: i["label"] for i in items}
    assert by_gid["g226"] == by_gid["g227"] == "russia_poland_airspace_violation"  # corrections applied


def test_gold_cluster_vectors_rows_match_ids():
    ids = _gold("cluster_vectors_ids.json")
    ids = ids["ids"] if isinstance(ids, dict) else ids
    vec = np.load(GOLD / "cluster_vectors.npy", mmap_mode="r", allow_pickle=False)
    assert vec.ndim == 2 and vec.shape[0] == len(ids)


def test_gold_fts_corpus_and_queries():
    corpus = _gold("fts_corpus.json")
    assert {k: len(v) for k, v in corpus.items()} == {"ko": 460, "zh": 177}
    queries = _gold("fts_queries.json")
    assert set(queries) == {"ko", "zh"}
    for lang in ("ko", "zh"):
        assert len(queries[lang]["known"]) == 10 and len(queries[lang]["nonsense"]) == 3


def test_gold_lang30():
    rows = _gold("lang30.json")
    assert len(rows) == 30 and len({r["title"] for r in rows}) == 30
    for lang in ("en", "ko", "zh"):
        assert sum(r["lang"] == lang for r in rows) == 10
    for r in rows:
        t = r["title"]
        hangul = sum("\uac00" <= ch <= "\ud7af" for ch in t)
        han = sum("\u4e00" <= ch <= "\u9fff" for ch in t)
        if r["lang"] == "ko":
            assert hangul > sum(ch.isalpha() for ch in t) / 2, t
        elif r["lang"] == "zh":
            assert hangul == 0 and han > 0, t
        else:
            assert hangul == 0 and han == 0 and any("a" <= ch.lower() <= "z" for ch in t), t
