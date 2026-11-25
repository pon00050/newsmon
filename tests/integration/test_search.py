"""Search (T-32): FR-20(a)(b)(c), AC-O1-06, NFR-10, on R6's frozen KO/ZH corpus (460 + 177 docs)."""
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pytest

from newsmon.domain.models import NormalisedItem
from newsmon.pipeline.normalise import normalise
from newsmon.web.service import Service
from tests.support.instance import make_app

pytestmark = pytest.mark.integration
GOLD = Path(__file__).resolve().parents[1] / "fixtures" / "gold"
NOW = datetime(2026, 11, 25, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def corpus_app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("search")
    src = {"key": "corpus", "name": "corpus", "access_method": "feed", "url": "https://corpus.example/rss",
           "storage": "metadata", "display": "snippet", "active": False}
    app = make_app(tmp, None, [src])
    ref = app.sources.source_by_key("corpus")
    corpus = json.loads((GOLD / "fts_corpus.json").read_text(encoding="utf-8"))
    docs = {}
    for lang, texts in corpus.items():
        for i, text in enumerate(texts):
            item = NormalisedItem(uri=f"{lang}-{i}", headline=text, language=lang,  # one column, as in R6
                                  source_key="corpus", connector_kind="feed", raw_ref="fixture", raw_sha256="0" * 64,
                                  parser="fixture", received_utc=NOW, licence_snapshot=ref.flags.snapshot_json())
            res = app.articles.store(ref, normalise(item), feed_id=None, now=NOW)
            docs[res.article_id] = (lang, unicodedata.normalize("NFC", text))
    yield app, docs
    app.close()


def truth(docs, lang, q):
    return {aid for aid, (l, t) in docs.items() if l == lang and q.lower() in t.lower()}


@pytest.mark.req("FR-20a", "NFR-10", "RA-09")
def test_known_answer_recall(corpus_app):
    app, docs = corpus_app
    queries = json.loads((GOLD / "fts_queries.json").read_text(encoding="utf-8"))
    report = []
    for lang in ("ko", "zh"):
        for q in queries[lang]["known"]:
            want = truth(docs, lang, q)
            got = {r["article_id"] for r in app.articles.search(q, lang=lang, limit=500)}
            assert want, f"control: {q} must have ground truth"
            report.append((lang, q, len(want & got), len(want)))
            assert want <= got, (lang, q, len(want - got))
    assert any(q in ("북한", "미국") for _, q, _, _ in report) and any(q in ("中国", "美国") for _, q, _, _ in report)
    print("FR-20a recall:", report)


@pytest.mark.req("FR-20b", "NFR-10", "RA-09")
def test_nonsense_returns_nothing(corpus_app):
    app, _ = corpus_app
    queries = json.loads((GOLD / "fts_queries.json").read_text(encoding="utf-8"))
    for lang in ("ko", "zh"):
        for q in queries[lang]["nonsense"]:
            assert app.articles.search(q, lang=lang) == [], q


@pytest.mark.req("FR-20c", "AC-O1-06")
def test_gazetteer_alias_expansion(tmp_path):
    src = {"key": "s", "name": "s", "access_method": "feed", "url": "https://s.example/rss", "active": False}
    app = make_app(tmp_path, None, [src])
    try:
        ref = app.sources.source_by_key("s")
        for uri, lang, head in [("k", "ko", "김여정, 한미연합훈련 비난 담화"), ("z", "zh", "金與正發表談話批評美韓軍演"),
                                ("e", "en", "Kim Yo Jong condemns drills"), ("x", "ko", "북한 경제 동향 분석")]:
            item = NormalisedItem(uri=uri, headline=head, language=lang, source_key="s", connector_kind="feed",
                                  raw_ref="t", raw_sha256="0" * 64, parser="t", received_utc=NOW,
                                  licence_snapshot=ref.flags.snapshot_json())
            app.articles.store(ref, normalise(item), feed_id=None, now=NOW)
        res = Service(app).search("Kim Yo Jong")
        langs = {r["lang"] for r in res["rows"]}
        assert {"ko", "zh", "en"} <= langs and "김여정" in res["aliases"]
        # AC-O1-06 known O1 limit: a non-gazetteer English phrase does not find Korean coverage
        assert {r["lang"] for r in Service(app).search("economic trends")["rows"]} <= {"en"}
    finally:
        app.close()


def test_fts_syntax_cannot_be_injected(corpus_app):
    app, _ = corpus_app
    for q in ['"', 'a OR', 'NEAR(', '*', 'headline_tok:x', '") OR ("']:
        app.articles.search(q)  # must not raise
