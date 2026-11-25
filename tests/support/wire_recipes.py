"""Run-time builders for wire fixtures that must not be committed (T-06, ADR-010 §3 and §8).

Stdlib only. The oversize file and the symlink escape are built in a test's tmp_path, never in the repo.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

WIRE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "wire"
INBOX_DIR = WIRE_DIR / "inbox"

_OVERSIZE_HEADER = (
    "SYNTHETIC: true\n"
    "ID: PTW-SYNTH-OVERSIZE-0001\n"
    "VERSION: 1\n"
    "VERSIONCREATED: 2026-11-24T09:00:00+00:00\n"
    "LANGUAGE: en\n"
    "URGENCY: 5\n"
    "SLUG: OVERSIZE-TEST\n"
    "HEADLINE: Synthetic oversize wire file for the size-limit check\n"
    "DATELINE: NOWHERE\n"
    "BODY:\n"
)
_OVERSIZE_PARAGRAPH = (
    "This synthetic paragraph is repeated to make a plain-text wire file larger than the watcher's size limit. "
    "It carries no news.\n\n"
)


def make_oversize(path: Path | str, size_bytes: int) -> Path:
    """Write a syntactically plausible plain-text wire file of exactly ``size_bytes`` bytes (ASCII)."""
    path = Path(path)
    header = _OVERSIZE_HEADER.encode("ascii")
    if size_bytes < len(header):
        raise ValueError(f"size_bytes must be at least {len(header)}")
    para = _OVERSIZE_PARAGRAPH.encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(header)
        remaining = size_bytes - len(header)
        chunk = para * max(1, (1 << 20) // len(para))
        while remaining >= len(chunk):
            fh.write(chunk)
            remaining -= len(chunk)
        while remaining >= len(para):
            fh.write(para)
            remaining -= len(para)
        fh.write(b"x" * remaining)
    return path


def make_symlink_escape(root: Path | str, outside_target: Path | str) -> Path | None:
    """Create ``root/synthetic_escape_link.txt`` pointing at ``outside_target`` (outside ``root``).

    Returns the link path, or None when the OS refuses to create symlinks (for example Windows without
    developer mode), so callers can ``pytest.skip``.
    """
    root = Path(root)
    target = Path(outside_target).resolve()
    root.mkdir(parents=True, exist_ok=True)
    link = root / "synthetic_escape_link.txt"
    if link.is_symlink() or link.exists():
        link.unlink()
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError, AttributeError):
        return None
    return link


def copy_inbox(dst: Path | str) -> list[Path]:
    """Copy every valid inbox file (including the .mp4) into ``dst``, keeping relative paths. Returns the copies."""
    dst = Path(dst)
    copied: list[Path] = []
    for src in sorted(p for p in INBOX_DIR.rglob("*") if p.is_file()):
        out = dst / src.relative_to(INBOX_DIR)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        copied.append(out)
    return copied
