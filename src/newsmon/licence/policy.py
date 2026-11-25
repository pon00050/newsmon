"""LicenceGate and DisplayPolicy (T-22, FR-06, FR-31(b)). Licence behaviour is configuration, never code: every decision
below reads the source's flags (snapshotted on the article at ingest). `synthetic` is provenance only and is never
consulted here (FR-27(d)).

Covered: storage gating, display gating for the web UI and search, and the AI-field rules of FR-06(f) (Release A.1).
Deferred: recipient gating (redistribution / authorised_users, with delivery) and retention purge (T-25).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from newsmon.domain.enums import Display, Storage
from newsmon.domain.models import LicenceFlags

SNIPPET_CHARS = 200


@dataclass(frozen=True)
class StoreDecision:
    store: bool  # storage=none: nothing is kept
    keep_description: bool
    keep_body: bool  # only storage=full keeps the body
    use_body_for_features: bool  # transient or full


class LicenceGate:
    @staticmethod
    def storage(flags: LicenceFlags) -> StoreDecision:
        s = flags.storage
        return StoreDecision(
            store=s is not Storage.NONE,
            keep_description=s is not Storage.NONE,
            keep_body=s is Storage.FULL,
            use_body_for_features=s in (Storage.TRANSIENT, Storage.FULL),
        )

    @staticmethod
    def may_fetch_body(flags: LicenceFlags) -> bool:
        """Article pages are requested only when storage is transient or full (FR-06(a))."""
        return flags.storage in (Storage.TRANSIENT, Storage.FULL)


def flags_from_snapshot(snapshot: str | dict) -> LicenceFlags:
    data = json.loads(snapshot) if isinstance(snapshot, str) else dict(snapshot)
    return LicenceFlags.model_validate(data)


def effective_display(flags: LicenceFlags, restrictions: str | None) -> Display:
    """The source's display level, capped at headline when the item carries any restriction we do not recognise.
    No restriction vocabulary is configured in the MVP, so every non-empty restriction caps display (FR-31(b))."""
    d = flags.display
    if restrictions and restrictions.strip() and d.rank > Display.HEADLINE.rank:
        return Display.HEADLINE
    return d


def safe_link(url: str | None) -> str | None:
    """Only http(s) links are ever rendered as links."""
    if url and url.lower().startswith(("http://", "https://")):
        return url
    return None


_URL = re.compile(r"(https?://|www\.)\S+", re.I)
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_TAG = re.compile(r"<[^>]*>")


def inert(text: str | None) -> str | None:
    """Model output as plain text: markup, markdown links and URLs removed (FR-25(a))."""
    if not text:
        return None
    t = _MD_LINK.sub(r"\1", str(text))
    t = _TAG.sub("", t)
    t = _URL.sub("", t)
    return " ".join(t.split()) or None


def _letters(s: str) -> str:
    """Text reduced to its letters and digits, case-folded, so that changing case, spacing or punctuation does not
    hide a copied run."""
    return "".join(c for c in unicodedata.normalize("NFKC", s or "").casefold() if c.isalnum())


def _shares_20_chars(ai_text: str, source: str) -> bool:
    src, a = _letters(source), _letters(ai_text)
    return any(a[i:i + 20] in src for i in range(0, max(0, len(a) - 19)))


def render_ai(ai: dict | None, flags: LicenceFlags, level: Display, source_text: str,
              restricted: bool = False) -> dict | None:
    """What of an AI assessment may be shown (FR-06(f)). Classification fields always; the Korean headline only if
    `translate` is permitted; the Korean summary only if `summarise` or `translate` is permitted; and for sources shown
    below snippet level no AI text that repeats 20 or more characters of the source. An item that carries a
    restriction shows no AI text at all: any that exists was made from the full text before the restriction arrived."""
    if not ai:
        return None
    out = ai.get("output") or {}
    ops = {str(o) for o in flags.permitted_ops}
    view = {
        "band": out.get("relevance_band"), "importance": out.get("importance"),
        "topics": [inert(t) for t in out.get("topics", []) if inert(t)][:5],
        "relevant_to": [{"target": inert(r.get("target")), "reason": inert(r.get("reason"))}
                        for r in out.get("relevant_to", []) if isinstance(r, dict) and inert(r.get("target"))][:8],
        "rationale": inert(out.get("rationale_ko")),
        "headline_ko": inert(out.get("headline_ko")) if "translate" in ops else None,
        "summary_ko": inert(out.get("summary_ko")) if ops & {"summarise", "translate"} else None,
        "model": ai.get("model"), "prompt_version": ai.get("prompt_version"), "generated_by_ai": True,
        "injection_suspected": bool(ai.get("injection_suspected")),
    }
    if restricted or level.rank < Display.HEADLINE.rank:  # nothing textual about a restricted or hidden item
        for k in ("headline_ko", "summary_ko", "rationale"):
            view[k] = None
        view["topics"], view["relevant_to"] = [], []
    elif level.rank < Display.SNIPPET.rank:  # no AI text may repeat 20+ characters of the source (FR-06(f))
        for k in ("headline_ko", "summary_ko", "rationale"):
            if view[k] and _shares_20_chars(view[k], source_text):
                view[k] = None
        view["topics"] = [t for t in view["topics"] if not _shares_20_chars(t, source_text)]
        view["relevant_to"] = [x for x in view["relevant_to"]
                               if not _shares_20_chars(x["target"] or "", source_text)
                               and not _shares_20_chars(x["reason"] or "", source_text)]
    return view


class DisplayPolicy:
    """One policy for every renderer (UI, search results; API, MCP, digest and export later)."""

    @staticmethod
    def render(article: dict[str, Any]) -> dict[str, Any]:
        """Return only the fields the article's licence snapshot allows to be shown.

        `article` needs: licence_snapshot, restrictions, headline, description_text, body_text, canonical_url, plus any
        metadata (source name, times, band, lang) which is always shown.
        """
        flags = flags_from_snapshot(article["licence_snapshot"])
        level = effective_display(flags, article.get("restrictions"))
        out = {k: article.get(k) for k in ("uid", "source_key", "source_name", "lang", "first_seen_utc",
                                           "published_utc", "final_band", "rule_score", "urgency", "status",
                                           "item_type", "located", "slugline")}
        out["display"] = str(level)
        out["link"] = safe_link(article.get("canonical_url"))
        out["headline"] = article.get("headline") if level.rank >= Display.HEADLINE.rank else None
        desc = article.get("description_text") or None
        if level is Display.SNIPPET and desc:
            out["summary"] = desc if len(desc) <= SNIPPET_CHARS else desc[:SNIPPET_CHARS].rstrip() + "…"
        elif level is Display.FULL:
            out["summary"] = desc
        else:
            out["summary"] = None
        out["body"] = article.get("body_text") if level is Display.FULL else None
        out["restricted"] = level is not flags.display
        source_text = " ".join(x for x in (article.get("headline"), article.get("description_text"),
                                           article.get("body_text")) if x)
        out["ai"] = render_ai(article.get("ai"), flags, level, source_text,
                              restricted=bool((article.get("restrictions") or "").strip()))
        return out
