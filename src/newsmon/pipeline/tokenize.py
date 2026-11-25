"""Search pre-tokenisation (T-32; korean_fts method D, recall 1.00 on KO/ZH). Pure: no I/O.

Latin/digit words are kept (lower-cased); every Hangul/Han run is split into overlapping character bigrams (a 1-char run
stays as is). The same function builds index text and query phrases: 대통령 -> "대통 통령".
"""
from __future__ import annotations

import re
import unicodedata

_CJK = "ᄀ-ᇿ㄰-㆏가-힯一-鿿㐀-䶿豈-﫿぀-ヿ"
_TOKEN = re.compile(rf"[{_CJK}]+|[^\W_{_CJK}]+", re.UNICODE)  # a Latin run never swallows adjacent CJK ("AP연합뉴스")
_CJK_RUN = re.compile(rf"^[{_CJK}]+$")


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for tok in _TOKEN.findall(unicodedata.normalize("NFKC", text or "")):
        if _CJK_RUN.match(tok):
            out += [tok] if len(tok) == 1 else [tok[i:i + 2] for i in range(len(tok) - 1)]
        else:
            out.append(tok.casefold())
    return out


def index_text(text: str) -> str:
    return " ".join(tokens(text))


def query_phrase(q: str) -> str | None:
    """One FTS5 phrase for a user term; None when the term has no searchable token. Quotes are dropped so user input
    can never inject FTS5 syntax."""
    toks = [t.replace('"', "") for t in tokens(q)]
    toks = [t for t in toks if t]
    if not toks:
        return None
    return '"' + " ".join(toks) + '"'


def build_match(query: str, aliases: dict[str, list[str]] | None = None) -> str | None:
    """Turn a user query into an FTS5 MATCH expression: whitespace-separated terms AND-ed; a double-quoted span is one
    phrase. `aliases` maps a term to alternative phrases (gazetteer expansion), OR-ed with it."""
    parts = re.findall(r'"([^"]+)"|(\S+)', query or "")
    clauses = []
    for quoted, bare in parts:
        term = quoted or bare
        alts = [term] + list((aliases or {}).get(term, []))
        phrases = [p for p in (query_phrase(a) for a in alts) if p]
        if phrases:
            clauses.append("(" + " OR ".join(dict.fromkeys(phrases)) + ")")
    return " AND ".join(clauses) or None
