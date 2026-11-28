"""Event tracking through the real pipeline: cycle stage, repository and read API, `newsmon events`. Synthetic feeds only.

Known-answer: one invented happening reported by three outlets becomes one event with three independent sources; a
near-duplicate copy follows its primary; a later report joins the stored event; a correction / kill shows as such.
No-answer: unrelated items and a nonsense item stay single. Licence: a headline the source may not display never
appears in the CLI output."""
import json
from xml.sax.saxutils import escape

import pytest

from newsmon.cli import main
from tests.support.clock import FrozenClock
from tests.support.fixture_server import Resp
from tests.support.instance import feed_source, make_app

pytestmark = pytest.mark.integration

START = "2026-11-26T09:00:00+00:00"

QUAKE = {
    "alpha": ("Strong earthquake strikes fictional Zorvania, thousands flee coastal towns",
              "A magnitude 7.1 earthquake hit Zorvania's northern coast, forcing thousands from their homes."),
    "beta": ("Zorvania earthquake: thousands evacuated after magnitude 7.1 quake",
             "Authorities in Zorvania evacuated coastal towns after the magnitude 7.1 earthquake."),
    "gamma": ("Magnitude 7.1 quake in Zorvania forces coastal evacuations",
              "Thousands left coastal towns in northern Zorvania after the earthquake, officials said."),
}
OTHER = {
    "alpha": ("Central bank of Quillmark holds interest rates steady", "Policy makers kept the benchmark rate unchanged."),
    "beta": ("Veltrano football club appoints new head coach", "The club named a former midfielder as its manager."),
    "gamma": ("Orbital cargo capsule docks with research station", "The uncrewed capsule delivered supplies."),
}
NONSENSE = ("Qxvt zzkp wvvb", "plorf grindle snark")


def rss(key: str, items: list[tuple[str, str, str]]) -> bytes:
    body = "".join(f"<item><title>{escape(t)}</title><link>https://www.{key}news.org/n/{gid}</link>"
                   f"<guid>{key}-{gid}</guid><description>{escape(d)}</description></item>" for gid, t, d in items)
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{key}</title>'
            f"<link>https://www.{key}news.org/</link><description>synthetic</description>{body}</channel></rss>").encode()


@pytest.fixture
def world(tmp_path, fixture_server):
    fixture_server.route("/robots.txt", Resp(body=b"User-agent: *\nAllow: /\n", content_type="text/plain"))
    feeds = {
        "alpha": [("q1", *QUAKE["alpha"]), ("o1", *OTHER["alpha"]), ("x1", *NONSENSE)],
        "beta": [("q1", *QUAKE["beta"]), ("o1", *OTHER["beta"])],
        "gamma": [("q1", *QUAKE["gamma"]), ("o1", *OTHER["gamma"])],
        "delta": [("c1", *QUAKE["alpha"])],  # a verbatim copy of alpha's report: a near-duplicate
        "hidden": [("h1", "Hiddenline canary about Zorvania earthquake evacuations", "not displayable")],
    }
    urls = {k: fixture_server.route(f"/{k}.xml", Resp(body=rss(k, v))) for k, v in feeds.items()}
    sources = [feed_source(k, u) for k, u in urls.items() if k != "hidden"]
    sources.append(feed_source("hidden", urls["hidden"], display="none"))
    clock = FrozenClock(START)
    app = make_app(tmp_path, fixture_server, sources, clock=clock)
    yield app, clock, fixture_server, tmp_path
    app.close()


def aid(app, key: str, gid: str) -> int:
    return app.db.scalar("SELECT a.article_id FROM article a JOIN source s USING (source_id) WHERE s.key = ? AND "
                         "a.canonical_url LIKE ?", (key, f"%/n/{gid}"))


def test_cycle_groups_the_same_happening_and_leaves_the_rest_single(world):
    app, _, _, _ = world
    rep = app.collect(force=True)
    assert rep.events_error is None and rep.events["placed"] > 0
    quake = {k: aid(app, k, "q1") for k in ("alpha", "beta", "gamma")}
    eids = {app.events.event_for_article(a) for a in quake.values()}
    assert len(eids) == 1 and None not in eids  # known answer: one event
    eid = eids.pop()
    copy = aid(app, "delta", "c1")
    assert app.db.scalar("SELECT dup_of FROM article WHERE article_id = ?", (copy,)) == quake["alpha"], "control: a dup"
    assert app.events.event_for_article(copy) == eid  # the copy follows its primary
    e = app.events.get(eid)
    assert e["primaries"] >= 3 and e["independent_sources"] >= 4 and e["status"] == "open"
    assert e["algo"].startswith("lexical-v1") and e["langs"] == ["en"]
    kinds = {m["article_id"]: m["kind"] for m in app.events.timeline(eid)}
    assert kinds[quake["alpha"]] == "first" and kinds[copy] == "repeat"
    assert kinds[quake["beta"]] == kinds[quake["gamma"]] == "development"
    # no-answer: unrelated items and the nonsense item are each alone
    for key, gid in (("alpha", "o1"), ("beta", "o1"), ("gamma", "o1"), ("alpha", "x1")):
        other = app.events.event_for_article(aid(app, key, gid))
        assert other is not None and other != eid and app.events.get(other)["members"] == 1
    multi = app.events.list_events(min_primaries=2)
    assert [x["event_id"] for x in multi] == [eid]
    assert multi[0]["lead"]["article_id"] == quake["alpha"]


def test_incremental_join_idempotent_and_rebuild_keeps_ids(world):
    app, clock, server, _ = world
    app.collect(force=True)
    eid = app.events.event_for_article(aid(app, "alpha", "q1"))
    before = app.db.query("SELECT event_id, article_id FROM event_member ORDER BY article_id")
    clock.advance(3600)
    server.route("/gamma.xml", Resp(body=rss("gamma", [
        ("q2", "Zorvania earthquake death toll rises as coastal towns evacuated", "Rescuers in Zorvania after the quake.")])))
    rep = app.collect(force=True)
    assert rep.events["joined"] == 1 and rep.events["created"] == 0
    assert app.events.event_for_article(aid(app, "gamma", "q2")) == eid
    after = app.db.query("SELECT event_id, article_id FROM event_member ORDER BY article_id")
    assert [tuple(r) for r in before] == [tuple(r) for r in after if r["article_id"] != aid(app, "gamma", "q2")]
    n = app.db.scalar("SELECT count(*) FROM event_member")
    rep = app.collect(force=True)  # nothing new: nothing moves, nothing is added
    assert rep.events["placed"] == 0 and app.db.scalar("SELECT count(*) FROM event_member") == n
    from newsmon.runtime.events import update_events
    update_events(app, rebuild=True)
    assert app.events.event_for_article(aid(app, "alpha", "q1")) == eid  # same first member, same id
    assert app.db.scalar("SELECT count(*) FROM event_member") == n


def test_corrections_and_kills_show_in_the_timeline(world):
    app, _, _, _ = world
    app.collect(force=True)
    beta, gamma = aid(app, "beta", "q1"), aid(app, "gamma", "q1")
    eid = app.events.event_for_article(beta)
    # ingestion does not yet mark corrections; the status column is what a correction sets
    app.db.execute("UPDATE article SET status = 'corrected' WHERE article_id = ?", (beta,))
    app.db.execute("UPDATE article SET status = 'killed' WHERE article_id = ?", (gamma,))
    kinds = {m["article_id"]: m["kind"] for m in app.events.timeline(eid)}
    assert kinds[beta] == "correction" and kinds[gamma] == "kill"


def test_an_event_defect_never_stops_the_cycle(world, monkeypatch):
    app, _, _, _ = world
    import newsmon.runtime.events as stage

    def boom(*a, **k):
        raise RuntimeError("synthetic event defect")
    monkeypatch.setattr(stage, "update_events", boom)
    rep = app.collect(force=True)
    assert rep.events is None and "synthetic event defect" in rep.events_error
    assert rep.new_articles > 0 and rep.alert_error is None and rep.alerts is not None
    assert app.db.scalar("SELECT count(*) FROM event") == 0


def test_switch_off(world):
    app, _, _, _ = world
    app.settings = app.settings.model_copy(update={"events": app.settings.events.model_copy(update={"enabled": False})})
    rep = app.collect(force=True)
    assert rep.events == {**rep.events, "enabled": False, "placed": 0}
    assert app.db.scalar("SELECT count(*) FROM event") == 0


def test_cli_builds_events_on_an_existing_database_and_respects_display(world, capsys):
    app, _, _, tmp = world
    app.settings = app.settings.model_copy(update={"events": app.settings.events.model_copy(update={"enabled": False})})
    app.collect(force=True)  # an existing database collected before events existed
    assert app.db.scalar("SELECT count(*) FROM event") == 0
    app.close()
    args = ["--config", str(tmp / "cfg"), "--data", str(tmp / "data")]
    assert main(["events", *args]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# 사건 목록") and QUAKE["beta"][0] in out and "최초" in out and "진전" in out
    assert OTHER["beta"][0] not in out  # single-item events are not listed by default
    assert "Hiddenline canary" not in out  # display=none: the headline is never shown
    assert main(["events", *args, "--json", "--min-members", "1", "--rebuild"]) == 0
    raw = capsys.readouterr().out
    doc = json.loads(raw)
    assert doc["pass"]["rebuilt"] and doc["algo"].startswith("lexical-v1")
    items = [m for e in doc["events"] for m in e["timeline"]]
    hidden = [m for m in items if m["source_key"] == "hidden"]
    assert hidden and all(m["headline"] is None for m in hidden)  # the link is shown, as in the queue
    assert "Hiddenline canary" not in raw
