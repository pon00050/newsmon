"""RSS/Atom connector (T-15; deliverable 10 row 1).

feedparser only ever parses bytes that HttpFetcher fetched; it never fetches a URL itself. A document that declares XML
entities (external-entity or entity-expansion attacks) is refused as a parse error before feedparser sees it.
"""
from __future__ import annotations

import calendar
import re
import xml.sax
from datetime import datetime, timezone

import feedparser

from newsmon.connectors.base import error, raw_unit
from newsmon.domain.enums import ErrorClass, PollStatus
from newsmon.domain.models import ConnectorHealth, NormalisedItem, PollResult, RawUnit
from newsmon.domain.ports import Clock, HttpFetcher
from newsmon.fetcher.robots import RobotsCache

PARSER = f"feedparser-{feedparser.__version__}"
_ENTITY_DECL = re.compile(rb"<!ENTITY", re.I)
_ENTITY_UTF16 = tuple(v.encode(enc) for v in ("<!ENTITY", "<!entity") for enc in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"))


_DECLARED = re.compile(rb"""<\?xml[^>]{0,200}?encoding\s*=\s*["']([A-Za-z0-9._:-]+)""")
# the encodings real feeds use; anything else (UTF-7, EBCDIC, ...) could spell an entity declaration unseen
_ENCODINGS = ("utf-8", "utf8", "utf-16", "utf-32", "us-ascii", "ascii", "iso-8859-", "latin", "windows-125", "cp125",
              "euc-kr", "ks_c_5601", "cp949", "gb2312", "gbk", "gb18030", "big5", "shift_jis", "shift-jis", "euc-jp")
_EBCDIC_XML = b"\x4c\x6f\xa7\x94"  # "<?xm" in EBCDIC


class FeedParseError(ValueError):
    pass


def parse_feed_bytes(payload: bytes):
    if _ENTITY_DECL.search(payload) or any(m in payload for m in _ENTITY_UTF16):
        raise FeedParseError("XML entity declaration refused")
    declared = _DECLARED.search(payload[:400])
    if payload.lstrip()[:4] == _EBCDIC_XML or (declared and not declared.group(1).decode().lower().startswith(_ENCODINGS)):
        raise FeedParseError("unsupported character encoding")
    d = feedparser.parse(payload)
    exc = d.get("bozo_exception") if d.get("bozo") else None
    if exc is not None and isinstance(exc, xml.sax.SAXException) and not isinstance(
            exc, (feedparser.CharacterEncodingOverride,)):
        raise FeedParseError(f"malformed XML: {exc.__class__.__name__}")
    if not d.get("version") and not d.entries:
        raise FeedParseError("not an RSS/Atom document")
    return d


def _when(entry, key: str) -> datetime | None:
    st = entry.get(f"{key}_parsed")
    if not st:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    except (OverflowError, ValueError, TypeError):
        return None


class FeedConnector:
    kind = "feed"

    def __init__(self, *, source_key: str, url: str, licence_snapshot: str, fetcher: HttpFetcher,
                 robots: RobotsCache | None, clock: Clock, lang_default: str | None = None, synthetic: bool = False,
                 etag: str | None = None, last_modified: str | None = None) -> None:
        self.source_key = source_key
        self.url = url
        self.licence_snapshot = licence_snapshot
        self.fetcher = fetcher
        self.robots = robots
        self.clock = clock
        self.lang_default = lang_default
        self.synthetic = synthetic
        self.etag = etag
        self.last_modified = last_modified
        self._health = ConnectorHealth()

    def poll(self, cursor: str | None = None) -> PollResult:
        if self.robots is not None:
            ok, status = self.robots.allowed(self.url)
            if not ok:
                if status == "ssrf_blocked":  # the host itself is refused; say so rather than blaming robots.txt
                    return error(ErrorClass.SSRF_BLOCKED, "destination address refused")
                return error(ErrorClass.ROBOTS, f"robots.txt disallows ({status})")
        r = self.fetcher.get(self.url, etag=self.etag, last_modified=self.last_modified)
        if r.status == 304:
            return PollResult(status=PollStatus.NOT_MODIFIED, http_status=304, etag=self.etag,
                              last_modified=self.last_modified)
        if r.error_class:
            return error(r.error_class, r.error_detail or "", r.status).model_copy(update={"bytes": len(r.body)})
        unit = raw_unit(self.url, r.body, self.clock.now(), http_status=r.status,
                        content_type=r.headers.get("content-type"))
        return PollResult(status=PollStatus.OK, http_status=r.status, raw_units=[unit], bytes=len(r.body),
                          etag=r.headers.get("etag"), last_modified=r.headers.get("last-modified"))

    def parse(self, raw: RawUnit) -> list[NormalisedItem]:
        d = parse_feed_bytes(raw.payload)
        feed_lang = (d.feed.get("language") or self.lang_default or None)
        items = []
        for e in d.entries:
            link = e.get("link") or None
            guid = e.get("id") or link
            published = _when(e, "published") or _when(e, "updated")
            summary = e.get("summary") or e.get("description") or None
            items.append(NormalisedItem(
                uri=guid, url=link, headline=e.get("title") or "", description_text=summary,
                versioncreated=published, published_raw=e.get("published") or e.get("updated") or "",
                language=feed_lang, source_key=self.source_key, connector_kind=self.kind, raw_ref=raw.raw_ref,
                raw_sha256=raw.raw_sha256, parser=PARSER, received_utc=raw.received_utc, synthetic=self.synthetic,
                licence_snapshot=self.licence_snapshot))
        return items

    def health(self) -> ConnectorHealth:
        return self._health
