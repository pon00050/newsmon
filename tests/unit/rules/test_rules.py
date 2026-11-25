"""Profiles and rules (T-30/T-31 essential portion): FR-16(b)(c), FR-17(b), keyword changes change ranking."""
from datetime import datetime, timedelta, timezone

import pytest

from newsmon.pipeline.normalise import fold
from newsmon.rules.engine import ItemFacts, evaluate
from newsmon.rules.profile import ProfileError, validate_profile

pytestmark = pytest.mark.unit
NOW = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
GAZ = {"kim_yo_jong": ["Kim Yo Jong", "김여정", "金與正"]}


def profile(**kw):
    d = {"key": "desk", "languages": ["en", "ko", "zh"],
         "topics": [{"label": "한반도", "keywords": {"ko": ["북한", "미사일"], "en": ["North Korea"]}}],
         "entities": ["kim_yo_jong"], "exclude_keywords": {"en": ["horoscope"]},
         "sources": {"prefer": {"wire": 2.0}, "mute": ["noisy"]},
         "priority_rules": [{"id": "wire_flash", "when": {"source_is_wire": True, "urgency_lte": 2}, "band": "flash"}]}
    d.update(kw)
    return validate_profile(d, source_keys={"wire", "noisy", "bbc"}, entity_ids=set(GAZ))


def facts(text, **kw):
    d = dict(text=fold(text), lang="en", source_key="bbc", is_wire=False, urgency=None, seen=NOW - timedelta(hours=1))
    d.update(kw)
    return ItemFacts(**d)


@pytest.mark.req("FR-16b")
def test_unknown_source_or_entity_rejected():
    with pytest.raises(ProfileError, match="unknown source"):
        profile(sources={"prefer": {"nope": 1.0}})
    with pytest.raises(ProfileError, match="unknown entity"):
        profile(entities=["nobody"])


@pytest.mark.req("FR-16c")
def test_flash_from_ai_field_rejected():
    with pytest.raises(ProfileError, match="flash cannot be set from an AI field"):
        profile(priority_rules=[{"id": "x", "when": {"ai_band": "flash"}, "band": "flash"}])


@pytest.mark.req("FR-17b", "RA-08")
def test_banded_items_explain_themselves():
    p = profile()
    ev = evaluate(p, facts("North Korea fires missile; Kim Yo Jong statement"), NOW, GAZ)
    assert ev.band in ("review", "report") and ev.score > 0
    ids = [h.rule_id for h in ev.hits]
    assert "topic:한반도" in ids and "entity:kim_yo_jong" in ids
    assert "North Korea" in ev.explanation


@pytest.mark.req("RA-08")
def test_adding_a_keyword_changes_ranking():
    text = "Taiwan Strait tensions rise"
    before = evaluate(profile(), facts(text), NOW, GAZ)
    p2 = profile(topics=[{"label": "미중", "keywords": {"en": ["Taiwan Strait"]}}])
    after = evaluate(p2, facts(text), NOW, GAZ)
    assert before.band == "drop" and after.band != "drop" and after.score > before.score


def test_flash_only_from_rules_and_drops():
    p = profile()
    assert evaluate(p, facts("anything", is_wire=True, urgency=1, source_key="wire"), NOW, GAZ).band == "flash"
    assert evaluate(p, facts("North Korea horoscope"), NOW, GAZ).band == "drop"
    assert evaluate(p, facts("North Korea", source_key="noisy"), NOW, GAZ).band == "drop"
    assert evaluate(p, facts("North Korea", lang="fr"), NOW, GAZ).band == "drop"
    # a high score alone never reaches flash
    many = evaluate(p, facts("North Korea missile Kim Yo Jong", independent_sources=9), NOW, GAZ)
    assert many.band == "report"


def test_cjk_substring_and_latin_word_boundary():
    p = profile()
    assert evaluate(p, facts("북한이 동해상으로", lang="ko"), NOW, GAZ).band != "drop"
    assert evaluate(p, facts("Northkoreanstyle"), NOW, GAZ).band == "drop"


def test_source_weight_scales_score():
    p = profile()
    base = evaluate(p, facts("North Korea", source_key="bbc"), NOW, GAZ).score
    boosted = evaluate(p, facts("North Korea", source_key="wire"), NOW, GAZ).score
    assert boosted == pytest.approx(base * 2.0, abs=0.01)
