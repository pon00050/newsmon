"""Public publication gate: what, if anything, of a stored article may appear on a public website.

Public redistribution is a separate permission from internal collection, storage, display and AI processing, and it is
denied by default. It comes from the source's *current* `sources.yaml` row (`public_redistribution` plus a written
`public_redistribution_basis`), so withdrawing it stops publication at the next export. Every internal restriction on
the article still applies on top: an item that is restricted, withheld, embargoed, withdrawn or customer-licensed, or
that may not be displayed internally, is never published.

What can be published is a closed list: link, source, times, rule band and score, our own topic and entity labels,
duplicate count, and (at `headline` level only) the headline. Descriptions, bodies, AI output, licence data and any
other stored field are never read into the public record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from newsmon.domain.enums import Display, LicenceOwner, Storage
from newsmon.licence.policy import flags_from_snapshot, safe_link
from newsmon.registry.loader import SourceSpec

LEVELS = ("none", "metadata", "headline")


@dataclass(frozen=True)
class PublicDecision:
    level: str  # none | metadata | headline
    reason: str = ""


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def decide(row: dict, spec: SourceSpec | None, now: datetime) -> PublicDecision:
    """The public level for one article row (from `ArticleRepo.public_candidates`) under the current source row."""
    if spec is None:
        return PublicDecision("none", "source no longer configured")
    if spec.public_redistribution == "none" or not (spec.public_redistribution_basis or "").strip():
        return PublicDecision("none", "public redistribution not permitted for this source")
    if spec.licence_owner is LicenceOwner.TENANT:
        return PublicDecision("none", "customer-licensed content")
    try:
        flags = flags_from_snapshot(row["licence_snapshot"])
    except Exception:  # an unreadable snapshot is never a permission
        return PublicDecision("none", "unreadable licence snapshot")
    if flags.licence_owner is LicenceOwner.TENANT:
        return PublicDecision("none", "customer-licensed content")
    if flags.storage is Storage.NONE or flags.display is Display.NONE:
        return PublicDecision("none", "not displayable internally")
    if row.get("status") in ("killed", "withdrawn", "gone"):
        return PublicDecision("none", f"item {row.get('status')}")
    if (row.get("restrictions") or "").strip():
        return PublicDecision("none", "item carries a restriction")
    if (row.get("pubstatus") or "usable") != "usable":
        return PublicDecision("none", f"pubstatus {row.get('pubstatus')}")
    emb = _parse(row.get("embargoed_utc"))
    if row.get("embargoed_utc") and (emb is None or emb > now):
        return PublicDecision("none", "embargoed")
    if not row.get("synthetic") and not safe_link(row.get("canonical_url")):  # real items always link to the publisher
        return PublicDecision("none", "no public http(s) link to attribute")
    return PublicDecision(spec.public_redistribution)


def public_record(row: dict, level: str) -> dict:
    """The closed public field list for one permitted article."""
    topics, entities = [], []
    for rid in row.get("rule_ids", []):
        if rid.startswith("topic:"):
            topics.append(rid[6:])
        elif rid.startswith("entity:"):
            entities.append(rid[7:])
    return {
        "uid": row["uid"],
        "source_key": row["source_key"],
        "source_name": row["source_name"],
        "lang": row.get("lang"),
        "published_utc": row.get("published_utc"),
        "first_seen_utc": row["first_seen_utc"],
        "headline": row.get("headline") if level == "headline" else None,
        "link": safe_link(row.get("canonical_url")),
        "band": row.get("final_band") or "drop",
        "score": round(float(row.get("rule_score") or 0.0), 3),
        "topics": topics[:8],
        "entities": entities[:8],
        "duplicates": int(row.get("dup_count") or 0),
        "synthetic": bool(row.get("synthetic")),
    }
