"""Fail if a folder about to be published contains something that must not be public.

    uv run python scripts/check_public_artifacts.py _site          # the built website
    uv run python scripts/check_public_artifacts.py . --repo       # the repository tree (skips .venv, _site, ...)

Checks: forbidden file types (databases, .env, archives, private corpus fixtures), credential patterns, local
absolute paths and the local account name, text that only exists in article bodies of the synthetic demo, and, for
every dashboard JSON (data/*.json), the public contract enforced by newsmon.publish.export.validate.
Controls: `--self-test` proves each pattern fires on a planted sample and stays silent on clean text.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

SKIP_DIRS = {".git", ".venv", "_site", "_build", "__pycache__", ".pytest_cache", "dist", "build", ".live-state"}
FORBIDDEN_NAMES = re.compile(r"(\.sqlite3?|\.db|\.sqlite-(wal|shm)|\.env|\.zip|\.7z|\.npy|\.jsonl|\.pyc)$|"
                             r"(^|/)tests/fixtures/(feeds|gold)/", re.I)
PATTERNS = {
    "anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "openai key": re.compile(r"\bsk-(proj-)?[A-Za-z0-9]{32,}"),
    "groq key": re.compile(r"\bgsk_[A-Za-z0-9]{30,}"),
    "github token": re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"),
    "aws key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "windows user path": re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+(?!<|\{|%|\$|Public\b|you\b|USER|runneradmin\b)", re.I),
    "local account name": re.compile(r"(?<![A-Za-z0-9])pon00(?![0-9])"),
    "synthetic body text": re.compile(r"\[SYNTHETIC DEMO\]"),
}
BODY_MARKER_ALLOWED = ("demo/", "tests/")
# Deliberate fakes in tests (a planted secret the config loader must refuse; a made-up Windows profile path).
ALLOW = {("tests/unit/config/test_no_secrets_in_yaml.py", "anthropic key"), ("tests/unit/test_desktop.py", "windows user path")}  # the marker legitimately appears in the generator and its tests
SELF_TEST = {
    "anthropic key": "x sk-ant-api03-" + "A" * 30, "github token": "ghp_" + "a" * 36,
    "private key": "-----BEGIN RSA PRIVATE KEY-----", "windows user path": r"C:\Users\someone\x",
    "local account name": "/c/Users/pon00/Projects", "synthetic body text": "[SYNTHETIC DEMO] Source",
}
CLEAN = "https://github.com/pon00050/newsmon C:\\Users\\<you>\\AppData %LOCALAPPDATA%\\Newsmon"


def scan(base: Path, repo: bool) -> list[str]:
    problems = []
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base).as_posix()
        if any(part in SKIP_DIRS for part in p.relative_to(base).parts) or not p.is_file():
            continue
        if FORBIDDEN_NAMES.search(rel):
            problems.append(f"{rel}: file type or location must not be published")
            continue
        if p.stat().st_size > 5_000_000:
            problems.append(f"{rel}: larger than 5 MB")
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, rx in PATTERNS.items():
            if name == "synthetic body text" and repo and rel.startswith(BODY_MARKER_ALLOWED):
                continue
            if rel == "scripts/check_public_artifacts.py" or (rel, name) in ALLOW:
                continue
            m = rx.search(text)
            if m:
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{rel}:{line}: {name}")
        if not repo and rel.startswith("data/") and rel.endswith(".json"):
            from newsmon.publish.export import PublicExportError, validate
            try:
                validate(json.loads(text))
            except (PublicExportError, ValueError, KeyError, TypeError) as exc:
                problems.append(f"{rel}: public contract: {exc}")
    return problems


def self_test() -> int:
    bad = [n for n, s in SELF_TEST.items() if not PATTERNS[n].search(s)]
    noisy = [n for n, rx in PATTERNS.items() if rx.search(CLEAN)]
    print(f"self-test: {len(SELF_TEST) - len(bad)}/{len(SELF_TEST)} planted samples caught; false positives: {noisy}")
    return 1 if bad or noisy else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="_site")
    ap.add_argument("--repo", action="store_true", help="scan a repository tree rather than a built site")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if self_test():
        return 1
    base = Path(a.path)
    if not base.is_dir():
        print(f"{base}: not a folder", file=sys.stderr)
        return 2
    problems = scan(base, a.repo)
    for p in problems:
        print(p, file=sys.stderr)
    print(f"{base}: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
