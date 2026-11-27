"""Watched inbox directory connector (T-33; FR-28; ADR-010 §3).

- read-only and confined to one root: symlinks that resolve outside it are refused (`error_class=io`); files are opened
  'rb' and never moved, renamed or deleted;
- polling scan, no OS events; a file is ready once its size and mtime are unchanged across two consecutive scans;
- the ledger (path, size, mtime, sha256) lives in the database; the connector asks it whether a version was already seen;
- files over `max_bytes` are refused; a file that disappears is reported as `gone` (never an error).
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from newsmon.connectors.base import error
from newsmon.connectors.wire import WireParseError, detect_format, media_kind, parse_wire
from newsmon.domain.enums import ErrorClass, PollStatus
from newsmon.domain.models import ConnectorHealth, NormalisedItem, PollResult, RawUnit
from newsmon.domain.ports import Clock

PARSER = "newsmon-wire-1"


@dataclass
class Refused:
    rel_path: str
    reason: str
    size: int = 0
    mtime_ns: int = 0
    sha256: str = ""


@dataclass
class ScanResult:
    ready: list[RawUnit] = field(default_factory=list)
    refused: list[Refused] = field(default_factory=list)
    gone: list[tuple[str, str]] = field(default_factory=list)
    waiting: int = 0  # files seen for the first time or still changing


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class DirectoryConnector:
    kind = "directory"

    def __init__(self, *, source_key: str, root: Path, licence_snapshot: str, clock: Clock,
                 seen: Callable[[str, str], bool], present: Callable[[], list[tuple[str, str]]],
                 max_bytes: int = 20 * 1024 * 1024, synthetic: bool = False, lang_default: str | None = None,
                 cursor: str | None = None) -> None:
        self.source_key = source_key
        self.root = Path(root)
        self.licence_snapshot = licence_snapshot
        self.clock = clock
        self.seen = seen
        self.present = present
        self.max_bytes = max_bytes
        self.synthetic = synthetic
        self.lang_default = lang_default
        self._last: dict[str, tuple[int, int]] = _load_cursor(cursor)
        self.last_scan = ScanResult()
        self._health = ConnectorHealth()

    def poll(self, cursor: str | None = None) -> PollResult:
        if not self.root.is_dir():
            return error(ErrorClass.IO, f"inbox root missing: {self.root}")
        scan = self.scan()
        self.last_scan = scan
        status = PollStatus.OK if scan.ready else PollStatus.EMPTY
        return PollResult(status=status, raw_units=scan.ready, bytes=sum(len(u.payload) for u in scan.ready),
                          next_cursor=self.cursor())

    def cursor(self) -> str:
        """The previous scan, persisted so the two-scan stability rule also holds across separate `collect` runs."""
        return json.dumps({k: list(v) for k, v in sorted(self._last.items())}, ensure_ascii=False)

    def scan(self) -> ScanResult:
        res = ScanResult()
        real_root = self.root.resolve()
        current: dict[str, tuple[int, int]] = {}
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            for name in sorted(filenames):
                p = Path(dirpath) / name
                rel = p.relative_to(self.root).as_posix()
                try:
                    real = p.resolve(strict=True)
                    if not real.is_relative_to(real_root):
                        res.refused.append(Refused(rel, "symlink escapes the inbox root"))
                        continue
                    st = real.stat()
                except (OSError, RuntimeError):
                    continue  # vanished between listing and stat: tolerated
                current[rel] = (st.st_size, st.st_mtime_ns)
                if self._last.get(rel) != current[rel]:
                    res.waiting += 1
                    continue  # first sighting or still being written
                try:
                    if st.st_size > self.max_bytes:
                        sha = _sha256_file(real)
                        if self.seen(rel, sha):
                            continue
                        with real.open("rb") as fh:
                            head = fh.read(16)
                        if media_kind(head) is None:  # an oversize text file is refused; a video is expected to be big
                            res.refused.append(Refused(rel, f"oversize ({st.st_size} bytes)", st.st_size, st.st_mtime_ns, sha))
                            continue
                        res.ready.append(RawUnit(raw_ref=rel, raw_sha256=sha, payload=head, received_utc=self.clock.now(),
                                                 meta={"rel_path": rel, "size": st.st_size, "mtime_ns": st.st_mtime_ns,
                                                       "abs_path": str(real), **_ap_name(name)}))
                        continue  # media is never read into memory whole, only its first bytes (type) and its hash
                    payload = real.read_bytes()
                except OSError:
                    continue
                sha = hashlib.sha256(payload).hexdigest()
                if self.seen(rel, sha):
                    continue
                res.ready.append(RawUnit(raw_ref=rel, raw_sha256=sha, payload=payload, received_utc=self.clock.now(),
                                         meta={"rel_path": rel, "size": st.st_size, "mtime_ns": st.st_mtime_ns,
                                               "abs_path": str(real), **_ap_name(name)}))
        listed = set(current)
        res.gone = [(rel, sha) for rel, sha in self.present() if rel not in listed]
        self._last = current
        return res

    def parse(self, raw: RawUnit) -> list[NormalisedItem]:
        fmt, items = parse_wire(raw.payload)
        out = []
        for d in items:
            ap_version = raw.meta.get("ap_version")
            embargoed = _dt(d["embargoed"])
            # anything that limits use of the item becomes a restriction: it caps display at the headline and keeps
            # the item away from AI processing, and it stays once set
            limits = [str(d["restrictions"]).strip() if d["restrictions"] else "",
                      "pubstatus: withheld" if d["pubstatus"] == "withheld" else "",
                      f"embargoed until {d['embargoed']}" if embargoed and embargoed > self.clock.now() else ""]
            out.append(NormalisedItem(
                uri=d["uri"], type=d["type"], version=d["version"] or ap_version or 1,
                firstcreated=_dt(d["firstcreated"]), versioncreated=_dt(d["versioncreated"]),
                published_raw=d["versioncreated"] or "", pubstatus=d["pubstatus"], headline=d["headline"] or "",
                slugline=d["slugline"], located=d["located"], language=d["language"] or self.lang_default,
                urgency=d["urgency"], description_text=d["description_text"], body_text=d["body_text"],
                renditions=d["renditions"], associations=d["associations"],
                restrictions="; ".join(x for x in limits if x) or None, embargoed=embargoed,
                media_refs=d["media_refs"], source_key=self.source_key, connector_kind=self.kind, raw_ref=raw.raw_ref,
                raw_sha256=raw.raw_sha256, parser=f"{PARSER}:{fmt}", received_utc=raw.received_utc,
                synthetic=self.synthetic, licence_snapshot=self.licence_snapshot))
        return out

    @staticmethod
    def classify(raw: RawUnit) -> str:
        return detect_format(raw.payload)

    @staticmethod
    def media_info(raw: RawUnit) -> tuple[str, str] | None:
        return media_kind(raw.payload[:16])

    def health(self) -> ConnectorHealth:
        return self._health


def _load_cursor(cursor: str | None) -> dict[str, tuple[int, int]]:
    try:
        return {k: (int(v[0]), int(v[1])) for k, v in json.loads(cursor).items()} if cursor else {}
    except (ValueError, TypeError, AttributeError, IndexError):
        return {}


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _ap_name(name: str) -> dict:
    """AP Media Agent style `ItemID--Version--ContentID.ext`."""
    stem = name.rsplit(".", 1)[0]
    parts = stem.split("--")
    if len(parts) == 3 and parts[1].isdigit():
        return {"ap_item_id": parts[0], "ap_version": int(parts[1]), "ap_content_id": parts[2]}
    return {}


__all__ = ["DirectoryConnector", "ScanResult", "Refused", "WireParseError"]
