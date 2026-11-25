"""Near-duplicate signatures and link decisions (T-20, FR-08; ADR-005). Pure: no I/O.

MinHash over character 4-grams, 128 permutations (datasketch). Thresholds: estimated Jaccard >= 0.9 -> same_item;
>= 0.5 -> syndicated (different source) or revision (same source, within 48 h). Live items are never near-dup linked.
A same-source `story_key` match within 48 h is a revision (Yonhap "(종합)").
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from datasketch import MinHash, MinHashLSH

NUM_PERM = 128
SHINGLE = 4
SAME_ITEM = 0.9
NEAR = 0.5
REVISION_WINDOW = timedelta(hours=48)
METHOD = f"minhash{NUM_PERM}-char{SHINGLE}"
SCHEME = MinHash(num_perm=NUM_PERM, seed=1).scheme  # datasketch 2.x requires it when rebuilding from stored values
MAX_CHARS = 1500  # headline + lead is what matters for duplicates; long bodies only dilute the signal


def shingles(text: str, k: int = SHINGLE) -> set[str]:
    t = " ".join(text.split())[:MAX_CHARS]
    if len(t) <= k:
        return {t} if t else set()
    return {t[i:i + k] for i in range(len(t) - k + 1)}


def signature(text: str) -> MinHash:
    m = MinHash(num_perm=NUM_PERM, seed=1)
    for s in shingles(text):
        m.update(s.encode("utf-8"))
    return m


def to_blob(m: MinHash) -> bytes:
    return np.asarray(m.hashvalues, dtype=np.uint64).tobytes()


def from_blob(blob: bytes) -> MinHash:
    return MinHash(num_perm=NUM_PERM, seed=1, hashvalues=np.frombuffer(blob, dtype=np.uint64).copy(), scheme=SCHEME)


def exact_jaccard(a: str, b: str) -> float:
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


@dataclass(frozen=True)
class Candidate:
    revision_id: int
    article_id: int
    source_id: int
    first_seen: datetime
    story_key: str | None
    is_live: bool


@dataclass(frozen=True)
class Link:
    other_revision_id: int
    other_article_id: int
    jaccard: float
    kind: str  # same_item | syndicated | revision


def classify(j: float, *, same_source: bool, within_window: bool) -> str | None:
    if j >= SAME_ITEM:
        return "same_item"
    if j >= NEAR:
        if not same_source:
            return "syndicated"
        if within_window:
            return "revision"
    return None


class NearDupIndex:
    """In-memory LSH over stored signatures; rebuilt from the database at start-up."""

    def __init__(self) -> None:
        self._lsh = MinHashLSH(threshold=NEAR, num_perm=NUM_PERM)
        self._sigs: dict[int, MinHash] = {}
        self._meta: dict[int, Candidate] = {}

    def __len__(self) -> int:
        return len(self._sigs)

    def add(self, cand: Candidate, sig: MinHash) -> None:
        if cand.revision_id in self._sigs or cand.is_live:
            return
        self._lsh.insert(str(cand.revision_id), sig)
        self._sigs[cand.revision_id] = sig
        self._meta[cand.revision_id] = cand

    def links_for(self, sig: MinHash, *, source_id: int, first_seen: datetime, story_key: str | None,
                  is_live: bool, exclude_article: int | None = None) -> list[Link]:
        if is_live:
            return []
        out: dict[int, Link] = {}
        for key in self._lsh.query(sig):
            c = self._meta[int(key)]
            if c.article_id == exclude_article:
                continue
            j = float(sig.jaccard(self._sigs[c.revision_id]))
            within = abs(first_seen - c.first_seen) <= REVISION_WINDOW
            kind = classify(j, same_source=c.source_id == source_id, within_window=within)
            if kind and (c.article_id not in out or out[c.article_id].jaccard < j):
                out[c.article_id] = Link(c.revision_id, c.article_id, j, kind)
        if story_key:
            for c in self._meta.values():
                if (c.source_id == source_id and c.story_key == story_key and c.article_id != exclude_article
                        and c.article_id not in out and abs(first_seen - c.first_seen) <= REVISION_WINDOW):
                    out[c.article_id] = Link(c.revision_id, c.article_id, 0.0, "revision")
        return sorted(out.values(), key=lambda link: -link.jaccard)
