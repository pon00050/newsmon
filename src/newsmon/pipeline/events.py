"""Event clustering and event timelines (ROADMAP "It lists items, not events"; ADR-005 AI-off path). Pure: no I/O.

An *event* is one happening reported by one or more items. Primary articles (not near-duplicates, not killed) are taken
in story-time order and placed by an incremental single pass: an article joins the most similar *live* event (one
updated within `window` of the article's own time) when the similarity is at or above `threshold`, and otherwise starts
a new event. Placed articles are never moved by a later pass.

Similarity is pluggable (`Vectorizer`): anything that turns a `Doc` into an L2-normalised sparse vector can be used, so a
cloud embedding model can be added later behind the same interface. The default is deterministic and needs no AI:
`LexicalVectorizer`, TF-IDF over folded headline + description with English word tokens (stop-words removed) and Korean
/ Chinese character bigrams (`pipeline.tokenize`), IDF fitted on the documents of the current window, cosine against the
event centroid. Tuned for precision: a wrong merge hides a story from the desk, a missed merge only shows two rows.

Story time is `published_utc` capped at `first_seen_utc` (`story_time`), so a feed that delivers a backlog of old items
on its first poll does not put stories weeks apart into one 48-hour window.

Timeline kinds (`timeline`) are derived at read time and never stored.
"""
from __future__ import annotations

import math
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from newsmon.pipeline.normalise import fold
from newsmon.pipeline.tokenize import tokens

ALGO = "lexical-v1"
DEFAULT_THRESHOLD = 0.35
DEFAULT_WINDOW = timedelta(hours=48)

# English function words and news filler that say nothing about which event an item reports. Kept short on purpose:
# IDF already discounts frequent words; this list removes the ones frequent enough to create false overlap in short
# headlines.
STOPWORDS_EN = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between both but
by can could did do does doing down during each few for from further had has have having he her here hers him his how
i if in into is it its itself just me more most my no nor not now of off on once only or other our out over own same
she should so some such than that the their them then there these they this those through to too under until up very
was we were what when where which while who whom why will with would you your yours says said say new news live update
updates latest report reports reported amid after over us via vs per its it's into onto
""".split())

ANCHOR_PREFIX = "@"  # a gazetteer entity anchor feature: "@<entity id>", shared by every language's names


def story_time(first_seen: datetime, published: datetime | None) -> datetime:
    """When the item happened for clustering purposes: its publication time, never later than when it was first seen."""
    return min(published, first_seen) if published is not None else first_seen


def features(headline: str | None, description: str | None = None, *, headline_weight: int = 2,
             anchors: Mapping[str, Sequence[str]] | None = None) -> Counter[str]:
    """The bag of informative tokens of one item. Headline tokens count `headline_weight` times. Latin tokens are
    case-folded words (stop-words, single letters and lone digits dropped); Hangul / Han runs become character bigrams.
    With `anchors` (entity id -> names in any language), an item naming an entity also gets the feature "@<id>"."""
    bag: Counter[str] = Counter()
    for text, weight in ((headline or "", headline_weight), (description or "", 1)):
        for t in tokens(fold(text)):
            t = _strip_accents(t)
            if _informative(t):
                bag[t] += weight
    if anchors:
        folded = fold(f"{headline or ''} {description or ''}")
        for eid, names in anchors.items():
            if any(_name_in(fold(n), folded) for n in names if n and n.strip()):
                bag[ANCHOR_PREFIX + eid] += headline_weight
    return bag


def _strip_accents(t: str) -> str:
    """"gérard" -> "gerard". Only Latin-script tokens: Hangul would decompose into jamo."""
    if t.isascii() or not any("LATIN" in unicodedata.name(c, "") for c in t):
        return t
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def _informative(t: str) -> bool:
    if t in STOPWORDS_EN:
        return False
    if t.isascii():
        if len(t) < 2:
            return False
        if t.isdigit() and len(t) < 3:
            return False
    return True


def _name_in(name: str, text: str) -> bool:
    if not name:
        return False
    if name.isascii():  # Latin names must match whole words: "un" must not hit "under"
        i = text.find(name)
        while i >= 0:
            before = text[i - 1] if i > 0 else " "
            after = text[i + len(name)] if i + len(name) < len(text) else " "
            if not before.isalnum() and not after.isalnum():
                return True
            i = text.find(name, i + 1)
        return False
    return name in text


# --- vectors -------------------------------------------------------------------------------------------------------------
Vector = dict[str, float]


@dataclass(frozen=True)
class Doc:
    """One item to cluster. `source` is its independence key (owner group, registrable domain or source key)."""
    article_id: int
    when: datetime
    bag: Counter[str]
    lang: str | None = None
    source: str = ""


class Vectorizer(Protocol):
    """Similarity plug-in. `fit` sees every document of the current window once; `vector` returns an L2-normalised
    sparse vector. Cosine against the event centroid is computed by the clusterer."""
    name: str

    def fit(self, docs: Iterable[Doc]) -> None: ...

    def vector(self, doc: Doc) -> Vector: ...


class LexicalVectorizer:
    """TF-IDF (sublinear tf, smoothed idf) over `Doc.bag`, IDF from the documents passed to `fit`."""
    name = ALGO

    def __init__(self) -> None:
        self.df: Counter[str] = Counter()
        self.n = 0

    def fit(self, docs: Iterable[Doc]) -> None:
        self.df = Counter()
        self.n = 0
        for d in docs:
            self.n += 1
            self.df.update(d.bag.keys())

    def idf(self, tok: str) -> float:
        return math.log((1 + self.n) / (1 + self.df.get(tok, 0))) + 1.0

    def vector(self, doc: Doc) -> Vector:
        v = {t: (1.0 + math.log(c)) * self.idf(t) for t, c in doc.bag.items() if c > 0}
        return _normalise(v)


def _normalise(v: Vector) -> Vector:
    norm = math.sqrt(sum(x * x for x in v.values()))
    return {k: x / norm for k, x in v.items()} if norm > 0 else {}


def cosine(a: Vector, b: Vector) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(k, 0.0) for k, x in a.items())


# --- clustering ----------------------------------------------------------------------------------------------------------
CANDIDATE_FEATURES = 12  # candidate events are found through a document's heaviest features (an inverted index)


@dataclass(frozen=True)
class Params:
    threshold: float = DEFAULT_THRESHOLD
    window: timedelta = DEFAULT_WINDOW
    min_shared: int = 2  # informative features shared with the event: one shared rare word never merges two items
    min_features: int = 2  # an item with fewer informative features never joins an event (it starts its own)
    cross_lang_threshold: float | None = None  # stricter bar when the item's language is not in the event (None = same)
    # stricter bar for joining an event only this item's own source has reported so far. Measured on a live copy:
    # most wrong merges were one source's recurring templated items (weather bulletins, results tables, daily briefings,
    # digests, market reports), which share their template words and differ only in the facts.
    same_source_threshold: float | None = 0.5


@dataclass
class EventState:
    key: object  # the event_id for a stored event, or ("new", article_id) for one started in this pass
    first: datetime
    last: datetime
    sums: Vector = field(default_factory=dict)  # sum of member vectors (centroid direction); its keys = the features
    norm2: float = 0.0  # squared length of `sums`, kept up to date on each add
    langs: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    size: int = 0

    def add(self, vec: Vector, doc: Doc | None = None) -> None:
        sums = self.sums
        for k, x in vec.items():
            old = sums.get(k, 0.0)
            new = old + x
            sums[k] = new
            self.norm2 += new * new - old * old
        if doc is not None:
            if doc.lang:
                self.langs.add(doc.lang)
            if doc.source:
                self.sources.add(doc.source)
            self.first = min(self.first, doc.when)
            self.last = max(self.last, doc.when)
        self.size += 1

    def score(self, vec: Vector) -> tuple[float, int]:
        """(cosine of `vec` to the centroid, number of features shared with the event)."""
        sums = self.sums
        dot, shared = 0.0, 0
        for k, x in vec.items():
            y = sums.get(k)
            if y is not None:
                dot += x * y
                shared += 1
        return (dot / math.sqrt(self.norm2) if self.norm2 > 0 else 0.0), shared


@dataclass(frozen=True)
class Placement:
    article_id: int
    event_key: object
    similarity: float | None  # None for the first item of a new event
    new_event: bool


@dataclass(frozen=True)
class Existing:
    """A stored event as the clusterer needs it: its window members (already placed) and its stored first/last times."""
    event_id: int
    first: datetime
    last: datetime
    members: tuple[Doc, ...]


def cluster(new: Sequence[Doc], existing: Sequence[Existing] = (), *, context: Sequence[Doc] = (),
            vectorizer: Vectorizer | None = None, params: Params = Params()) -> list[Placement]:
    """Place `new` documents (in story-time order) into `existing` events or new ones. IDF is fitted on every document
    of the window: `new`, the existing members and any other `context` documents. Returns one placement per new doc."""
    vz = vectorizer or LexicalVectorizer()
    window_docs = {d.article_id: d for d in (*context, *(m for e in existing for m in e.members), *new)}
    vz.fit(window_docs.values())
    index: dict[str, list[EventState]] = {}  # feature -> events that have it: only those can share features

    for e in existing:
        st = EventState(e.event_id, e.first, e.last)
        for m in e.members:
            vec = vz.vector(m)
            for k in vec:
                if k not in st.sums:
                    index.setdefault(k, []).append(st)
            st.add(vec, None)
            if m.lang:
                st.langs.add(m.lang)
            if m.source:
                st.sources.add(m.source)
    out: list[Placement] = []
    for d in sorted(new, key=lambda x: (x.when, x.article_id)):
        vec = vz.vector(d)
        best, best_s = None, 0.0
        if len(vec) >= params.min_features:
            candidates: dict[int, EventState] = {}
            for k in sorted(vec, key=vec.__getitem__, reverse=True)[:CANDIDATE_FEATURES]:
                for st in index.get(k, ()):
                    candidates[id(st)] = st
            for ev in candidates.values():
                if ev.last < d.when - params.window or ev.first > d.when + params.window:
                    continue
                s, shared = ev.score(vec)
                if shared < params.min_shared:
                    continue
                bar = params.threshold
                if params.cross_lang_threshold is not None and d.lang and ev.langs and d.lang not in ev.langs:
                    bar = max(bar, params.cross_lang_threshold)
                if params.same_source_threshold is not None and d.source and ev.sources == {d.source}:
                    bar = max(bar, params.same_source_threshold)
                if s >= bar and (s > best_s or (s == best_s and best is not None and _older(ev, best))):
                    best, best_s = ev, s
        target = best or EventState(("new", d.article_id), d.when, d.when)
        for k in vec:
            if k not in target.sums:
                index.setdefault(k, []).append(target)
        target.add(vec, d)
        if best is None:
            out.append(Placement(d.article_id, target.key, None, True))
        else:
            out.append(Placement(d.article_id, best.key, round(best_s, 4), False))
    return out


def _older(a: EventState, b: EventState) -> bool:
    return a.first < b.first


# --- timeline ------------------------------------------------------------------------------------------------------------
KINDS = ("first", "repeat", "development", "correction", "withdrawal", "kill")
NOVEL_NEW_SOURCE = 0.0  # a new independent source is a development however it words the story (it confirms it)
NOVEL_SAME_SOURCE = 0.5  # a source updating its own story must bring this share of new features to be a development


@dataclass(frozen=True)
class Member:
    """One event member as `timeline` needs it (any order; `timeline` sorts by story time, then article id)."""
    article_id: int
    when: datetime
    bag: Counter[str]
    source: str
    dup_of: int | None = None
    status: str = "live"
    change_kinds: tuple[str, ...] = ()


@dataclass(frozen=True)
class Step:
    article_id: int
    kind: str
    novelty: float  # share of this item's features absent from every earlier member (1.0 for the first)
    new_source: bool  # its independence key had not appeared earlier in the event


def timeline(members: Sequence[Member]) -> list[Step]:
    """Derive each member's kind. Rules, first match wins:
    `kill` / `withdrawal` / `correction` from the article status or any revision's change kind; `first` for the earliest
    member; `repeat` for a near-duplicate of another member; `development` when it brings a new independent source,
    or when a source that already reported the event adds novelty >= NOVEL_SAME_SOURCE; otherwise `repeat` (a same-source
    update, or an item that adds almost nothing the event did not already have)."""
    out: list[Step] = []
    seen_feats: set[str] = set()
    seen_sources: set[str] = set()
    member_ids = {m.article_id for m in members}
    for i, m in enumerate(sorted(members, key=lambda x: (x.when, x.article_id))):
        feats = set(m.bag)
        novelty = 1.0 if i == 0 else (len(feats - seen_feats) / len(feats) if feats else 0.0)
        new_source = m.source not in seen_sources
        ck = set(m.change_kinds)
        if m.status == "killed" or "kill" in ck:
            kind = "kill"
        elif m.status in ("withdrawn", "gone") or "withdrawal" in ck:
            kind = "withdrawal"
        elif m.status == "corrected" or "correction" in ck:
            kind = "correction"
        elif i == 0:
            kind = "first"
        elif m.dup_of is not None and m.dup_of in member_ids:
            kind = "repeat"
        elif (new_source and novelty >= NOVEL_NEW_SOURCE) or novelty >= NOVEL_SAME_SOURCE:
            kind = "development"
        else:
            kind = "repeat"
        out.append(Step(m.article_id, kind, round(novelty, 3), new_source))
        seen_feats |= feats
        seen_sources.add(m.source)
    return out
