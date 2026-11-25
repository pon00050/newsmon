"""Rule-based relevance with explanation (T-31 essential portion; FR-17). Pure: no I/O.

score = topic hits + watch-entity hits + extra terms + wire urgency + independent sources + recency, times the source
weight. Bands: priority rules (highest wins) or score thresholds; `flash` only ever comes from an explicit rule.
Mutes, excluded keywords and languages outside the profile give `drop`.

Deferred to the event layer: event size and the spike flag (they need T-27 / T-29).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

from newsmon.pipeline.normalise import fold
from newsmon.rules.profile import Profile

BAND_RANK = {"drop": 0, "review": 1, "report": 2, "flash": 3}
_CJK = re.compile(r"[ᄀ-ᇿ㄰-㆏가-힯一-鿿㐀-䶿぀-ヿ]")


@lru_cache(maxsize=4096)
def _term_rx(term: str) -> re.Pattern:
    t = fold(term)
    if _CJK.search(t):
        return re.compile(re.escape(t))  # CJK: substring (no word boundaries in the script)
    return re.compile(r"(?<![\w])" + re.escape(t) + r"(?![\w])")


def find_terms(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t and _term_rx(t).search(text)]


@dataclass(frozen=True)
class ItemFacts:
    """What the rules see about one item (already normalised and folded)."""

    text: str  # folded headline + description (+ body when stored)
    lang: str | None
    source_key: str
    is_wire: bool
    urgency: int | None
    seen: datetime
    independent_sources: int = 1


@dataclass
class Hit:
    rule_id: str
    matched: str
    score: float


@dataclass
class Evaluation:
    band: str
    score: float
    hits: list[Hit] = field(default_factory=list)

    @property
    def explanation(self) -> str:
        return "; ".join(f"{h.rule_id}" + (f" [{h.matched}]" if h.matched else "") for h in self.hits)


def evaluate(p: Profile, f: ItemFacts, now: datetime, entity_names: dict[str, list[str]] | None = None) -> Evaluation:
    hits: list[Hit] = []
    w = p.weights
    if f.source_key in p.sources.mute:
        return Evaluation("drop", 0.0, [Hit("source_muted", f.source_key, 0.0)])
    if p.languages and f.lang and f.lang not in p.languages:
        return Evaluation("drop", 0.0, [Hit("language_excluded", f.lang, 0.0)])
    excluded = find_terms(f.text, [t for terms in p.exclude_keywords.values() for t in terms])
    if excluded:
        return Evaluation("drop", 0.0, [Hit("excluded_keyword", ", ".join(excluded), 0.0)])

    score = 0.0
    topic_hit = False
    for topic in p.topics:
        matched = find_terms(f.text, [t for terms in topic.keywords.values() for t in terms])
        if matched:
            topic_hit = True
            s = topic.weight * w.topic_hit + w.keyword_extra * (len(matched) - 1)
            score += s
            hits.append(Hit(f"topic:{topic.label}", ", ".join(matched), s))
    entity_hit = False
    for eid in p.entities:
        matched = find_terms(f.text, (entity_names or {}).get(eid, []))
        if matched:
            entity_hit = True
            score += w.entity_hit
            hits.append(Hit(f"entity:{eid}", ", ".join(matched), w.entity_hit))
    if f.is_wire and f.urgency is not None and 1 <= f.urgency <= 8:
        s = (9 - f.urgency) / 8 * w.wire_urgency
        score += s
        hits.append(Hit("wire_urgency", str(f.urgency), s))
    if f.independent_sources > 1:
        s = w.independent_source * (f.independent_sources - 1)
        score += s
        hits.append(Hit("independent_sources", str(f.independent_sources), s))
    age_h = max(0.0, (now - f.seen).total_seconds() / 3600)
    if score > 0 and age_h < w.recency_hours:
        s = w.recency * (1 - age_h / w.recency_hours)
        score += s
        hits.append(Hit("recency", f"{age_h:.1f}h", s))
    weight = p.sources.prefer.get(f.source_key, 1.0)
    if weight != 1.0 and score > 0:
        hits.append(Hit("source_weight", f"x{weight}", 0.0))
    score *= weight

    band = "drop"
    if score >= p.thresholds.report_score:
        band = "report"
    elif score >= p.thresholds.review_score:
        band = "review"
    facts = {"source_is_wire": f.is_wire, "urgency": f.urgency, "topic_hit": topic_hit, "entity_hit": entity_hit,
             "keyword_hit": topic_hit or entity_hit, "independent_sources": f.independent_sources, "age_h": age_h,
             "lang": f.lang, "source_key": f.source_key}
    for rule in p.priority_rules:
        if _when(rule.when, facts) and BAND_RANK[rule.band] > BAND_RANK[band]:
            band = rule.band
            hits.append(Hit(f"rule:{rule.id}", "", 0.0))
    return Evaluation(band, round(score, 3), hits)


def _when(cond: dict, facts: dict) -> bool:
    for k, v in cond.items():
        if k == "source_is_wire" and facts["source_is_wire"] != bool(v):
            return False
        if k == "urgency_lte" and not (facts["urgency"] is not None and facts["urgency"] <= v):
            return False
        if k in ("topic_hit", "entity_hit", "keyword_hit") and facts[k] != bool(v):
            return False
        if k == "independent_sources_gte" and facts["independent_sources"] < v:
            return False
        if k == "within_hours" and facts["age_h"] > v:
            return False
        if k == "lang_in" and facts["lang"] not in v:
            return False
        if k == "source_in" and facts["source_key"] not in v:
            return False
    return True
