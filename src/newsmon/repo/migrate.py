"""Migration runner: plain SQL files plus a version table (T-07, deliverable 10 row 23)."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib import resources

from newsmon.repo.db import Database


def _migrations() -> list[tuple[int, str, str]]:
    out = []
    for f in resources.files("newsmon.repo").joinpath("migrations").iterdir():
        if f.name.endswith(".sql"):
            out.append((int(f.name.split("_", 1)[0]), f.name, f.read_text(encoding="utf-8")))
    return sorted(out)


def current_version(db: Database) -> int:
    if not db.one("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"):
        return 0
    return db.scalar("SELECT COALESCE(MAX(version), 0) FROM schema_version") or 0


def pending(db: Database) -> list[str]:
    v = current_version(db)
    return [name for num, name, _ in _migrations() if num > v]


def migrate(db: Database) -> list[str]:
    """Apply pending migrations; return the names applied. Each file runs in one transaction."""
    applied = []
    db.script("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL, applied_utc TEXT NOT NULL);")
    v = current_version(db)
    for num, name, sql in _migrations():
        if num <= v:
            continue
        with db.lock:
            try:
                db.script("BEGIN;\n" + sql)
                db.execute("INSERT INTO schema_version (version, applied_utc) VALUES (?, ?)",
                           (num, datetime.now(timezone.utc).isoformat(timespec="seconds")))
                db.execute("COMMIT")
            except Exception:
                if db.con.in_transaction:
                    db.execute("ROLLBACK")
                raise
        applied.append(name)
    return applied


def ensure_workspace(db: Database, name: str, use_context: str, now_utc: str) -> int:
    row = db.one("SELECT workspace_id, use_context FROM workspace WHERE workspace_id = 1")
    if row is None:
        db.execute("INSERT INTO workspace (workspace_id, name, use_context, created_utc) VALUES (1, ?, ?, ?)",
                   (name, use_context, now_utc))
    elif row["use_context"] != use_context:
        db.execute("UPDATE workspace SET use_context = ? WHERE workspace_id = 1", (use_context,))
    return 1
