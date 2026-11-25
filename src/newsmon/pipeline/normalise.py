"""Normalisation and quarantine decisions (T-18, FR-05). Pure functions: no I/O (NFR-21).

- canonical URL: courlan (non-strict: drops tracking parameters, keeps real query keys) plus our own fragment strip;
- text: HTML stripped to inert text (script/style content dropped), entities unescaped, NFC, whitespace collapsed;
- language: script ratio (Hangul / Han / kana / Latin), feed metadata as the tie-breaker for Latin text;
- time: UTC, with the raw string kept; a missing or unparseable date stays NULL (never dropped, FR-05(a));
- per-source boilerplate strip with regex validation (TS-SEC-23);
- content_sha256 over NFKC-folded headline + description + body.
"""
from __future__ import annotations

import hashlib
import html
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser

import courlan

from newsmon.domain.models import NormalisedItem

# --- URLs ----------------------------------------------------------------------------------------------------------


def canonical_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    u = url.strip()
    if not re.match(r"^https?://", u, re.I):
        return None
    try:
        norm = courlan.normalize_url(u, strict=False)
    except Exception:  # courlan raises on some malformed inputs
        norm = u
    return norm.split("#", 1)[0] or None


# --- text ------------------------------------------------------------------------------------------------------------
class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template", "iframe", "object"}
    _BLOCK = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag in self._BLOCK:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        elif tag in self._BLOCK:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


_WS = re.compile(r"\s+")
_CTRL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​-‏‪-‮⁠-⁤﻿]")


def clean_text(value: str | None, *, keep_paragraphs: bool = False) -> str:
    """HTML -> inert plain text. With keep_paragraphs, blank-line paragraph breaks survive."""
    if not value:
        return ""
    s = value
    if "<" in s and ">" in s:
        p = _TextExtractor()
        try:
            p.feed(s)
            p.close()
            s = "".join(p.parts)
        except Exception:
            s = re.sub(r"<[^>]*>", " ", s)
    s = html.unescape(s)
    s = unicodedata.normalize("NFC", _CTRL.sub("", s))
    if keep_paragraphs:
        paras = [_WS.sub(" ", x).strip() for x in re.split(r"\n\s*\n", s)]
        return "\n\n".join(x for x in paras if x)
    return _WS.sub(" ", s).strip()


def fold(text: str) -> str:
    """Matching form: NFKC, case-folded, whitespace-collapsed."""
    return _WS.sub(" ", unicodedata.normalize("NFKC", text).casefold()).strip()


# --- language --------------------------------------------------------------------------------------------------------
def script_counts(text: str) -> dict[str, int]:
    c = {"hangul": 0, "han": 0, "kana": 0, "latin": 0}
    for ch in text:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
            c["hangul"] += 1
        elif 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF:
            c["han"] += 1
        elif 0x3040 <= o <= 0x30FF:
            c["kana"] += 1
        elif ch.isascii() and ch.isalpha() or 0x00C0 <= o <= 0x024F:
            c["latin"] += 1
    return c


def detect_lang(text: str, hint: str | None = None) -> str | None:
    c = script_counts(text)
    letters = sum(c.values())
    hint = (hint or "").split("-")[0].lower() or None
    if letters == 0:
        return hint
    if c["hangul"] / letters >= 0.2:
        return "ko"
    if c["kana"] / letters >= 0.1:
        return "ja"
    if c["han"] / letters >= 0.3:
        return "zh"
    if hint and hint not in ("ko", "zh", "ja"):
        return hint
    return "en" if c["latin"] else hint


# --- time ------------------------------------------------------------------------------------------------------------
def to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else to_utc(dt).isoformat(timespec="seconds")


# --- boilerplate rules -------------------------------------------------------------------------------------------------
class RegexRejected(ValueError):
    pass


_NESTED_QUANT = re.compile(r"\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)\s*[+*{]")


def compile_rule(pattern: str, *, max_len: int = 300, trial_ms: float = 50.0) -> re.Pattern:
    """Compile a configured pattern after validation: length cap, no nested quantifiers, and a timed trial on
    adversarial strings (TS-SEC-23)."""
    if len(pattern) > max_len:
        raise RegexRejected(f"pattern longer than {max_len} characters")
    if _NESTED_QUANT.search(pattern):
        raise RegexRejected("nested quantifier (catastrophic backtracking risk)")
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        raise RegexRejected(f"invalid regex: {exc}") from None
    for probe in ("a" * 25 + "!", "가" * 25 + "\n", " " * 25 + "x"):
        t0 = time.perf_counter()
        rx.search(probe)
        if (time.perf_counter() - t0) * 1000 > trial_ms:
            raise RegexRejected("pattern too slow on the trial string")
    return rx


@dataclass(frozen=True)
class SourceRules:
    boilerplate: tuple[re.Pattern, ...] = ()
    live: tuple[re.Pattern, ...] = ()
    story_key: re.Pattern | None = None

    @classmethod
    def build(cls, boilerplate=(), live=(), story_key: str | None = None) -> "SourceRules":
        return cls(tuple(compile_rule(p) for p in boilerplate or ()), tuple(compile_rule(p) for p in live or ()),
                   compile_rule(story_key) if story_key else None)


# --- the normalised record -----------------------------------------------------------------------------------------------
@dataclass
class Normalised:
    item: NormalisedItem  # cleaned copy
    canonical_url: str | None
    lang: str | None
    published_utc: str | None
    published_raw: str
    content_sha256: str
    match_text: str  # folded headline + description + body, for dedup and rules
    story_key: str | None = None
    is_live: bool = False
    warnings: list[str] = field(default_factory=list)


class Quarantined(Exception):
    """The record failed validation; the reason is stored in `quarantine`."""


def content_hash(headline: str, description: str, body: str) -> str:
    return hashlib.sha256(fold(" ".join(x for x in (headline, description, body) if x)).encode("utf-8")).hexdigest()


def normalise(item: NormalisedItem, rules: SourceRules | None = None, *, lang_hint: str | None = None) -> Normalised:
    rules = rules or SourceRules()
    headline = clean_text(item.headline)
    if not headline:
        raise Quarantined("empty title")
    description = clean_text(item.description_text)
    body = clean_text(item.body_text, keep_paragraphs=True)
    for rx in rules.boilerplate:
        description = rx.sub("", description).strip()
        body = rx.sub("", body).strip()
    lang = detect_lang(headline + " " + description, item.language or lang_hint)
    cleaned = item.model_copy(update={"headline": headline, "description_text": description or None,
                                      "body_text": body or None, "language": lang,
                                      "slugline": clean_text(item.slugline) or None,
                                      "located": clean_text(item.located) or None})
    story_key = None
    if rules.story_key is not None:
        story_key = fold(rules.story_key.sub("", headline))
    is_live = any(rx.search(headline) for rx in rules.live)
    return Normalised(
        item=cleaned,
        canonical_url=canonical_url(item.url),
        lang=lang,
        published_utc=iso(item.versioncreated),
        published_raw=item.published_raw or "",
        content_sha256=content_hash(headline, description, body),
        match_text=fold(" ".join(x for x in (headline, description, body) if x)),
        story_key=story_key,
        is_live=is_live,
    )
