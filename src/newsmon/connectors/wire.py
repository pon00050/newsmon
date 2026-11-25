"""Wire-format detection and parsers (T-34; FR-29; ADR-010 §3). Format is detected by content, never by extension.

- NewsML-G2 (IPTC G2 namespace, newsItem / newsMessage), NITF (root `nitf`), ninjs (JSON with ninjs keys), and the
  project's plain-text wire (tests/fixtures/wire/plain/FORMAT.md);
- XML goes through defusedxml: entity declarations and external references are refused (FR-29(d));
- media files (detected by magic bytes) become `media_asset` references only, never copies (FR-29(e)).

`parse_wire()` returns plain dicts in the golden-JSON shape so the field mapping can be checked field by field, plus
`embargoed` (UTC ISO or None) where the format carries a release time.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import defusedxml.ElementTree as DET
from defusedxml import DefusedXmlException

G2_NS = "http://iptc.org/std/nar/2006-10-01/"
WS = re.compile(r"\s+")

FIELDS = ("uri", "version", "type", "headline", "slugline", "located", "language", "urgency", "versioncreated",
          "firstcreated", "pubstatus", "description_text", "body_text", "associations", "renditions", "restrictions",
          "media_refs")


class WireParseError(ValueError):
    pass


# --- detection --------------------------------------------------------------------------------------------------------
def media_kind(head: bytes) -> tuple[str, str] | None:
    """(kind, content_type) for media files recognised by magic bytes."""
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video", "video/mp4"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "video", "video/webm"
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return "audio", "audio/mpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio", "audio/wav"
    return None


def detect_format(data: bytes) -> str:
    """'newsml_g2' | 'nitf' | 'ninjs' | 'plain' | 'media' | 'unknown'."""
    if media_kind(data[:16]):
        return "media"
    text = data[:4096].lstrip(b"\xef\xbb\xbf").lstrip()
    if text.startswith(b"<"):
        if G2_NS.encode() in data[:8192] and (b"newsItem" in data[:8192] or b"newsMessage" in data[:8192]):
            return "newsml_g2"
        if re.search(rb"<nitf[\s>]", data[:8192]):
            return "nitf"
        return "unknown"
    if text.startswith(b"{"):
        try:
            obj = json.loads(data.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            return "ninjs"  # looks like JSON; the parser will quarantine it as malformed
        if isinstance(obj, dict) and ("uri" in obj or "headline" in obj or "versioncreated" in obj):
            return "ninjs"
        return "unknown"
    try:
        head = data[:4096].decode("utf-8-sig")
    except UnicodeDecodeError:
        return "unknown"
    keys = {m.group(1) for m in re.finditer(r"^([A-Z]+):", head, re.M)}
    if {"HEADLINE", "BODY"} & keys and len(keys & {"ID", "SLUG", "HEADLINE", "DATELINE", "URGENCY", "BODY"}) >= 2:
        return "plain"
    return "unknown"


# --- helpers ----------------------------------------------------------------------------------------------------------
def collapse(s: str | None) -> str | None:
    if s is None:
        return None
    s = WS.sub(" ", s).strip()
    return s or None


def paragraphs(parts: list[str]) -> str | None:
    paras = [collapse(p) for p in parts]
    paras = [p for p in paras if p]
    return "\n\n".join(paras) if paras else None


def utc_iso(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    v = value.strip()
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})([+-]\d{4}|Z)?", v)
    if m:  # ISO basic format (NITF date.issue@norm)
        y, mo, d, h, mi, s, off = m.groups()
        v = f"{y}-{mo}-{d}T{h}:{mi}:{s}" + ("" if not off else ("+00:00" if off == "Z" else f"{off[:3]}:{off[3:]}"))
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise WireParseError("unparseable timestamp") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lang_tag(tag: str | None) -> str | None:
    return tag.split("-")[0].lower() if tag else None


def _int(v: Any) -> int | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return int(str(v).strip())
    except ValueError:
        raise WireParseError("a numeric field is not an integer") from None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(el, *path: str):
    cur = [el]
    for name in path:
        nxt = []
        for c in cur:
            nxt += [x for x in c if _local(x.tag) == name]
        cur = nxt
    return cur


def _first(el, *path: str):
    found = _find(el, *path)
    return found[0] if found else None


def _text(el) -> str:
    return "".join(el.itertext()) if el is not None else ""


def _xml(data: bytes):
    try:
        return DET.fromstring(data)
    except DefusedXmlException as exc:
        raise WireParseError(f"unsafe XML refused: {exc.__class__.__name__}") from None
    except Exception as exc:  # ParseError and friends
        raise WireParseError(f"malformed XML: {exc.__class__.__name__}") from None


def _item(**kw) -> dict[str, Any]:
    d = {f: None for f in FIELDS}
    d.update(associations={}, renditions=[], media_refs=[], type="text", pubstatus="usable", version=1, embargoed=None)
    d.update(kw)
    if not d["headline"]:
        raise WireParseError("item has no headline")
    if not d["uri"]:
        raise WireParseError("item has no id")
    return d


# --- NewsML-G2 --------------------------------------------------------------------------------------------------------
def parse_g2(data: bytes) -> list[dict]:
    root = _xml(data)
    items = [root] if _local(root.tag) == "newsItem" else _find(root, "itemSet", "newsItem")
    if not items:
        raise WireParseError("NewsML-G2 document without newsItem")
    out = []
    for it in items:
        meta, cm = _first(it, "itemMeta"), _first(it, "contentMeta")
        if meta is None or cm is None:
            raise WireParseError("newsItem without itemMeta/contentMeta")
        cls = (_first(meta, "itemClass").get("qcode", "ninat:text") if _first(meta, "itemClass") is not None else "ninat:text")
        status = _first(meta, "pubStatus")
        desc = [d for d in _find(cm, "description") if d.get("role", "drol:summary") == "drol:summary"]
        body = [_text(p) for p in _find(it, "contentSet", "inlineXML", "html", "body", "p")]
        if not body:
            body = [_text(p) for p in _find(it, "contentSet", "inlineXML") for p in p.iter() if _local(p.tag) == "p"]
        lang = _first(cm, "language")
        out.append(_item(
            uri=it.get("guid"), version=_int(it.get("version")) or 1, type=cls.split(":", 1)[-1],
            headline=collapse(_text(_first(cm, "headline"))), slugline=collapse(_text(_first(cm, "slugline"))),
            located=collapse(_text(_first(cm, "located", "name"))), language=lang_tag(lang.get("tag") if lang is not None else it.get("{http://www.w3.org/XML/1998/namespace}lang")),
            urgency=_int(_text(_first(cm, "urgency")) or None), versioncreated=utc_iso(_text(_first(meta, "versionCreated"))),
            firstcreated=utc_iso(_text(_first(meta, "firstCreated"))),
            pubstatus=(status.get("qcode", "stat:usable").split(":", 1)[-1] if status is not None else "usable"),
            description_text=collapse(_text(desc[0])) if desc else None, body_text=paragraphs(body),
            embargoed=utc_iso(_text(_first(meta, "embargoed")))))
    return out


# --- NITF -------------------------------------------------------------------------------------------------------------
def parse_nitf(data: bytes) -> list[dict]:
    root = _xml(data)
    if _local(root.tag) != "nitf":
        raise WireParseError("not a NITF document")
    docdata = _first(root, "head", "docdata")
    if docdata is None:
        raise WireParseError("NITF without docdata")
    docid, urg, issue, dukey, release = (_first(docdata, n) for n in ("doc-id", "urgency", "date.issue", "du-key",
                                                                      "date.release"))
    blocks = _find(root, "body", "body.content", "block")
    story, shot = [], []
    for b in blocks:
        ps = [_text(p) for p in b if _local(p.tag) == "p"]
        (shot if b.get("class") == "shotlist" else story).extend(ps)
    if not blocks:
        story = [_text(p) for p in _find(root, "body", "body.content", "p")]
    assoc = {"shotlist": "\n".join(x for x in (collapse(s) for s in shot) if x)} if shot else {}
    abstract = _first(root, "body", "body.head", "abstract")
    return [_item(
        uri=docid.get("id-string") if docid is not None else None, version=_int(dukey.get("version")) if dukey is not None else 1,
        headline=collapse(_text(_first(root, "body", "body.head", "hedline", "hl1"))),
        slugline=dukey.get("key") if dukey is not None else None,
        located=collapse(_text(_first(root, "body", "body.head", "dateline", "location", "city"))),
        language=lang_tag(root.get("baselang")), urgency=_int(urg.get("ed-urg")) if urg is not None else None,
        versioncreated=utc_iso(issue.get("norm")) if issue is not None else None,
        pubstatus=docdata.get("management-status", "usable"),
        description_text=collapse(_text(abstract)) if abstract is not None else None,
        body_text=paragraphs(story), associations=assoc,
        embargoed=utc_iso(release.get("norm")) if release is not None else None)]


# --- ninjs -------------------------------------------------------------------------------------------------------------
def parse_ninjs(data: bytes) -> list[dict]:
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise WireParseError(f"malformed JSON: {exc.__class__.__name__}") from None
    if not isinstance(obj, dict):
        raise WireParseError("ninjs document is not an object")
    rends = obj.get("renditions") or []
    if not isinstance(rends, list):
        raise WireParseError("renditions is not a list")
    body = obj.get("body_text")
    return [_item(
        uri=obj.get("uri"), version=_int(obj.get("version")) or 1, type=obj.get("type") or "text",
        headline=collapse(obj.get("headline")), slugline=collapse(obj.get("slugline")),
        located=collapse(obj.get("located")) if isinstance(obj.get("located"), str) else None,
        language=lang_tag(obj.get("language")), urgency=_int(obj.get("urgency")),
        versioncreated=utc_iso(obj.get("versioncreated")), firstcreated=utc_iso(obj.get("firstcreated")),
        pubstatus=obj.get("pubstatus") or "usable", description_text=collapse(obj.get("description_text")),
        body_text=paragraphs(re.split(r"\n\s*\n", body)) if isinstance(body, str) else None,
        associations=obj.get("associations") or {}, renditions=rends, restrictions=obj.get("restrictions"),
        embargoed=utc_iso(obj.get("embargoed")),
        media_refs=[r["href"] for r in rends if isinstance(r, dict) and r.get("href")])]


# --- plain-text wire -----------------------------------------------------------------------------------------------------
def parse_plain(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise WireParseError("plain wire is not UTF-8") from None
    head, sep, body = text.replace("\r\n", "\n").partition("\nBODY:\n")
    if not sep:
        if text.startswith("BODY:\n"):
            head, body = "", text[6:]
        else:
            raise WireParseError("plain wire without a BODY: line")
    h: dict[str, str] = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip().isupper():
                h[k.strip()] = v.strip()
    for req in ("ID", "HEADLINE"):
        if not h.get(req):
            raise WireParseError(f"plain wire missing {req}")
    return [_item(
        uri=h["ID"], version=_int(h.get("VERSION")) or 1, type=(h.get("TYPE") or "text").lower(),
        headline=collapse(h["HEADLINE"]), slugline=h.get("SLUG") or None, located=h.get("DATELINE") or None,
        language=lang_tag(h.get("LANGUAGE")), urgency=_int(h.get("URGENCY")),
        versioncreated=utc_iso(h.get("VERSIONCREATED")), firstcreated=utc_iso(h.get("FIRSTCREATED")),
        pubstatus=(h.get("PUBSTATUS") or "usable").lower(), description_text=h.get("DESCRIPTION") or None,
        body_text=paragraphs(re.split(r"\n\s*\n", body)), restrictions=h.get("RESTRICTIONS") or None)]


PARSERS = {"newsml_g2": parse_g2, "nitf": parse_nitf, "ninjs": parse_ninjs, "plain": parse_plain}


def parse_wire(data: bytes) -> tuple[str, list[dict]]:
    fmt = detect_format(data)
    if fmt not in PARSERS:
        raise WireParseError(f"unrecognised format ({fmt})")
    try:
        items = PARSERS[fmt](data)
    except WireParseError:
        raise
    except Exception as exc:  # a field of the wrong type (a headline that is an object, a number where text belongs)
        raise WireParseError(f"malformed {fmt}: {exc.__class__.__name__}") from None
    for it in items:
        if it["pubstatus"] not in ("usable", "withheld", "canceled"):
            raise WireParseError("unknown pubstatus")
        if it["type"] not in ("text", "video", "audio", "picture"):
            it["type"] = "text"
    return fmt, items
