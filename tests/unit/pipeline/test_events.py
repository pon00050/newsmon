"""Event clustering and timeline kinds (pipeline/events.py), synthetic text only.

Known-answer controls: differently worded reports of one happening from several sources land in one event; a correction,
withdrawal or kill is recognised as such. No-answer controls: unrelated items stay single; a nonsense item joins
nothing; the same words outside the window start a new event; one source's templated bulletins do not chain."""
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from newsmon.pipeline import events as ev

pytestmark = pytest.mark.unit

T0 = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)

# one invented happening, three outlets, three wordings
QUAKE = [
    ("Strong earthquake strikes fictional Zorvania, thousands flee coastal towns",
     "A magnitude 7.1 earthquake hit Zorvania's northern coast on Thursday, forcing thousands from their homes."),
    ("Zorvania earthquake: thousands evacuated after magnitude 7.1 quake",
     "Authorities in Zorvania evacuated coastal towns after the magnitude 7.1 earthquake."),
    ("Magnitude 7.1 quake in Zorvania forces coastal evacuations",
     "Thousands left coastal towns in northern Zorvania after the earthquake, officials said."),
]
UNRELATED = [
    ("Central bank of Quillmark holds interest rates steady", "Policy makers kept the benchmark rate unchanged."),
    ("Veltrano football club appoints new head coach", "The club named a former midfielder as its manager."),
    ("Orbital cargo capsule docks with research station", "The uncrewed capsule delivered supplies and experiments."),
    ("Farmers protest grain import rules in Dravonia", "Tractors blocked roads around the capital over tariffs."),
]


def doc(i: int, headline: str, description: str = "", *, hours: float = 0, source: str = "", lang: str = "en"):
    return ev.Doc(article_id=i, when=T0 + timedelta(hours=hours), bag=Counter(ev.features(headline, description)),
                  lang=lang, source=source or f"src{i}")


def groups(placements):
    out: dict = {}
    for p in placements:
        out.setdefault(p.event_key, []).append(p.article_id)
    return sorted(sorted(g) for g in out.values())


def test_features_fold_stopwords_bigrams_and_accents():
    f = ev.features("The Quake in Zorvania", "Gérard said", headline_weight=2)
    assert f["quake"] == 2 and f["zorvania"] == 2 and f["gerard"] == 1
    assert "the" not in f and "in" not in f and "said" not in f
    ko = ev.features("대통령 방문", None, headline_weight=1)
    assert set(ko) == {"대통", "통령", "방문"}  # Hangul runs become character bigrams


def test_anchor_features_match_names_in_any_language_as_whole_words():
    anchors = {"zorvania_pm": ["Arlo Venn", "아를로 벤"], "un": ["UN"]}
    assert ev.ANCHOR_PREFIX + "zorvania_pm" in ev.features("아를로 벤 총리 사임", anchors=anchors)
    assert ev.ANCHOR_PREFIX + "zorvania_pm" in ev.features("Arlo Venn resigns", anchors=anchors)
    assert ev.ANCHOR_PREFIX + "un" not in ev.features("Floods under control", anchors=anchors)


def test_known_answer_same_happening_three_sources_one_event():
    docs = [doc(i + 1, h, d, hours=i) for i, (h, d) in enumerate(QUAKE)]
    docs += [doc(10 + i, h, d, hours=0.5 + i) for i, (h, d) in enumerate(UNRELATED)]
    placements = ev.cluster(docs)
    assert [1, 2, 3] in groups(placements)
    joined = [p for p in placements if p.article_id in (2, 3)]
    assert all(not p.new_event and p.similarity >= ev.DEFAULT_THRESHOLD for p in joined)


def test_no_answer_unrelated_items_and_nonsense_stay_single():
    docs = [doc(10 + i, h, d, hours=i) for i, (h, d) in enumerate(UNRELATED)]
    docs += [doc(1, *QUAKE[0], hours=0.2), doc(99, "Qxvt zzkp wvvb", "plorf grindle snark", hours=1)]
    placements = ev.cluster(docs)
    assert all(len(g) == 1 for g in groups(placements))
    assert all(p.new_event and p.similarity is None for p in placements)


def test_an_item_with_too_few_features_never_joins():
    placements = ev.cluster([doc(1, *QUAKE[0]), doc(2, "Zorvania", "", hours=1)])
    assert groups(placements) == [[1], [2]]


def test_window_same_words_outside_window_start_a_new_event():
    placements = ev.cluster([doc(1, *QUAKE[0]), doc(2, *QUAKE[1], hours=49)], params=ev.Params(window=timedelta(hours=48)))
    assert groups(placements) == [[1], [2]]
    placements = ev.cluster([doc(1, *QUAKE[0]), doc(2, *QUAKE[1], hours=47)], params=ev.Params(window=timedelta(hours=48)))
    assert groups(placements) == [[1, 2]]


def test_one_sources_templated_bulletins_need_the_stricter_bar():
    a = doc(1, "Gale warning issued for northern sea area Kestrel", "", source="wx")
    b = doc(2, "Gale warning issued for southern sea area Plover", "", hours=1, source="wx")
    loose = ev.Params(threshold=0.2, same_source_threshold=None)
    assert groups(ev.cluster([a, b], params=loose)) == [[1, 2]], "control: the template alone clears the main bar"
    strict = ev.Params(threshold=0.2, same_source_threshold=0.95)
    assert groups(ev.cluster([a, b], params=strict)) == [[1], [2]]


def test_existing_events_are_extended_and_never_reshuffled():
    old = ev.Existing(event_id=7, first=T0, last=T0 + timedelta(hours=1),
                      members=(doc(1, *QUAKE[0]), doc(2, *QUAKE[1], hours=1)))
    placements = ev.cluster([doc(3, *QUAKE[2], hours=2), doc(4, *UNRELATED[0], hours=2)], [old])
    by = {p.article_id: p for p in placements}
    assert by[3].event_key == 7 and not by[3].new_event
    assert by[4].new_event
    assert {p.article_id for p in placements} == {3, 4}  # stored members are context, never re-placed


def test_cross_language_threshold_applies_only_when_the_language_is_new():
    a = doc(1, "Zorvania APEC summit opens in Lindor", "", lang="en")
    b = doc(2, "Zorvania APEC summit Lindor 개막", "", hours=1, lang="ko")
    assert groups(ev.cluster([a, b], params=ev.Params(threshold=0.2))) == [[1, 2]], "control: shared Latin tokens link"
    assert groups(ev.cluster([a, b], params=ev.Params(threshold=0.2, cross_lang_threshold=0.99))) == [[1], [2]]


def test_story_time_caps_publication_at_first_seen():
    assert ev.story_time(T0, T0 - timedelta(days=30)) == T0 - timedelta(days=30)
    assert ev.story_time(T0, T0 + timedelta(hours=5)) == T0  # a future-dated feed entry
    assert ev.story_time(T0, None) == T0


def member(i, headline, description="", *, hours=0, source="", **kw):
    return ev.Member(article_id=i, when=T0 + timedelta(hours=hours), bag=Counter(ev.features(headline, description)),
                     source=source or f"src{i}", **kw)


def test_timeline_kinds_known_answers():
    steps = ev.timeline([
        member(1, *QUAKE[0], source="a"),
        member(2, *QUAKE[0], hours=0.5, source="b", dup_of=1),  # a near-duplicate copy
        member(3, *QUAKE[1], hours=1, source="c"),  # a new independent source
        member(4, QUAKE[0][0] + " update", QUAKE[0][1], hours=2, source="a"),  # same source, nothing new
        member(5, "Zorvania aftershock topples bridge, rescuers search rubble", "Rescue teams search", hours=3, source="a"),
        member(6, *QUAKE[2], hours=4, source="d", status="corrected"),
        member(7, *QUAKE[2], hours=5, source="e", change_kinds=("initial", "withdrawal")),
        member(8, *QUAKE[2], hours=6, source="f", status="killed"),
    ])
    kinds = {s.article_id: s.kind for s in steps}
    assert kinds == {1: "first", 2: "repeat", 3: "development", 4: "repeat", 5: "development", 6: "correction",
                     7: "withdrawal", 8: "kill"}
    by = {s.article_id: s for s in steps}
    assert by[1].novelty == 1.0 and by[4].novelty < ev.NOVEL_SAME_SOURCE <= by[5].novelty
    assert by[3].new_source and not by[4].new_source


def test_timeline_orders_by_story_time_not_input_order():
    steps = ev.timeline([member(2, *QUAKE[1], hours=1), member(1, *QUAKE[0])])
    assert [s.article_id for s in steps] == [1, 2] and steps[0].kind == "first"
