"""TS-FR05a-d, TS-SEC-06 (T-18) and TS-SEC-23 (regex guard)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from newsmon.domain.models import LicenceFlags, NormalisedItem
from newsmon.pipeline.normalise import (
    Quarantined, RegexRejected, SourceRules, canonical_url, clean_text, compile_rule, detect_lang, normalise,
)

pytestmark = pytest.mark.unit
GOLD = Path(__file__).resolve().parents[2] / "fixtures" / "gold"
NOW = datetime(2026, 11, 25, tzinfo=timezone.utc)


def item(**kw) -> NormalisedItem:
    base = dict(headline="Title", source_key="s", connector_kind="feed", raw_ref="r", raw_sha256="0" * 64,
                parser="test", received_utc=NOW, licence_snapshot=LicenceFlags().snapshot_json())
    base.update(kw)
    return NormalisedItem(**base)


@pytest.mark.req("FR-05a")
def test_missing_pubdate():
    n = normalise(item(versioncreated=None, published_raw=""))
    assert n.published_utc is None and n.published_raw == ""
    # first_seen is set at persistence time; the item is kept, not dropped
    assert n.item.headline == "Title"


@pytest.mark.req("FR-05b")
def test_lang30():
    rows = json.loads((GOLD / "lang30.json").read_text(encoding="utf-8"))
    assert len(rows) == 30
    wrong = [(r["title"], r["lang"], detect_lang(r["title"])) for r in rows if detect_lang(r["title"]) != r["lang"]]
    assert len(rows) - len(wrong) >= 29, wrong


@pytest.mark.req("FR-05c")
def test_canonical():
    assert canonical_url("https://www.bbc.com/news/articles/abc123?at_medium=RSS&at_campaign=rss#frag") == \
        "https://www.bbc.com/news/articles/abc123"
    assert canonical_url("https://www.khan.co.kr/a/1?utm_source=rss&id=5#x") == "https://www.khan.co.kr/a/1?id=5"
    assert canonical_url("javascript:alert(1)") is None and canonical_url("") is None


@pytest.mark.req("FR-05d")
def test_empty_title():
    with pytest.raises(Quarantined, match="empty title"):
        normalise(item(headline="   "))
    with pytest.raises(Quarantined):
        normalise(item(headline="<b> </b>"))


def test_utc_and_raw_kept():
    t = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
    n = normalise(item(versioncreated=t, published_raw="Wed, 25 Nov 2026 18:00:00 +0900"))
    assert n.published_utc == "2026-11-25T09:00:00+00:00"
    assert n.published_raw == "Wed, 25 Nov 2026 18:00:00 +0900"


def test_html_stripped():
    raw = 'Hi <script>alert(1)</script><img src=x onerror=alert(1)> <a href="javascript:alert(1)">x</a> &amp; bye'
    out = clean_text(raw)
    assert "<" not in out and "alert" not in out and "javascript" not in out
    assert out == "Hi x & bye"
    n = normalise(item(headline="<i>Big</i> news", description_text=raw))
    assert n.item.headline == "Big news" and "script" not in (n.item.description_text or "")


def test_content_hash_ignores_case_and_spacing():
    a = normalise(item(headline="Hello  World", description_text="A b"))
    b = normalise(item(headline="hello world", description_text=" a   B "))
    assert a.content_sha256 == b.content_sha256


def test_story_key_and_live():
    rules = SourceRules.build(live=[r"(?i)\blive\b\s*:"], story_key=r"\s*\((종합|[0-9]+보)\)\s*$")
    a = normalise(item(headline="북한, 탄도미사일 발사(종합)"), rules)
    b = normalise(item(headline="북한, 탄도미사일 발사"), rules)
    assert a.story_key == b.story_key
    assert normalise(item(headline="Ukraine war live: day 1000"), rules).is_live


@pytest.mark.parametrize("pattern", ["(a+)+$", "(\\w*)*x", "x" * 400])
def test_regex_guard_rejects(pattern):
    with pytest.raises(RegexRejected):
        compile_rule(pattern)


def test_regex_guard_accepts_normal():
    assert compile_rule(r"\s*\((종합|[0-9]+보)\)\s*$").search("x(종합)")


def test_tokenizer_splits_latin_glued_to_hangul():
    from newsmon.pipeline.tokenize import index_text, query_phrase
    ix = index_text("AP연합뉴스이스라엘군의 공습")
    assert ix.startswith("ap 연합 합뉴") and "이스 스라 라엘" in ix
    assert query_phrase("대통령") == '"대통 통령"'
