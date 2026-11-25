"""SQLite connection factory and the single-writer discipline (T-07, ADR-004).

One `Database` owns one connection (WAL, foreign keys, busy timeout). Every statement runs under one re-entrant lock,
which serialises writers inside the process: the "single writer" of 11 §0 without a separate thread or queue. This is
the simplest mechanism that gives "no 'database is locked'" for one desk (TS-DB-02); a second process still relies on
WAL + busy_timeout.

`ident()` and `qmarks()` are the only helpers allowed inside an SQL f-string (TS-ARCH-06): `ident` admits identifiers
from a fixed allow-list, `qmarks` emits '?' placeholders.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def ident(names: str | Iterable[str], allowed: Iterable[str] | None = None) -> str:
    """Comma-join vetted identifiers. Raises unless every name is a plain lower-case identifier (and allowed)."""
    seq = [names] if isinstance(names, str) else list(names)
    allow = set(allowed) if allowed is not None else None
    for n in seq:
        if not _IDENT.match(n) or (allow is not None and n not in allow):
            raise ValueError(f"refused SQL identifier {n!r}")
    return ", ".join(seq)


def qmarks(n: int) -> str:
    if n < 1:
        raise ValueError("qmarks needs n >= 1")
    return ", ".join("?" * n)


class Database:
    def __init__(self, path: Path | str, *, read_only: bool = False) -> None:
        self.path = Path(path) if str(path) != ":memory:" else path
        self.read_only = read_only
        if read_only:
            uri = f"file:{Path(path).as_posix()}?mode=ro"
            self.con = sqlite3.connect(uri, uri=True, check_same_thread=False, isolation_level=None)
        else:
            if isinstance(self.path, Path):
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self.con = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self._tx_depth = 0
        self.trace: list[str] | None = None
        with self.lock:
            self.con.execute("PRAGMA foreign_keys = ON")
            self.con.execute("PRAGMA busy_timeout = 10000")
            if not read_only and str(path) != ":memory:":
                self.con.execute("PRAGMA journal_mode = WAL")
                self.con.execute("PRAGMA synchronous = NORMAL")

    # --- tracing (tests: NFR-23 query log) ---------------------------------------------------------------------------
    def enable_trace(self) -> list[str]:
        self.trace = []
        self.con.set_trace_callback(self.trace.append)
        return self.trace

    # --- statements ---------------------------------------------------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] | dict = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.con.execute(sql, params)

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> sqlite3.Cursor:
        with self.lock:
            return self.con.executemany(sql, rows)

    def query(self, sql: str, params: Sequence[Any] | dict = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.con.execute(sql, params).fetchall()

    def one(self, sql: str, params: Sequence[Any] | dict = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.con.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] | dict = ()) -> Any:
        row = self.one(sql, params)
        return None if row is None else row[0]

    @contextmanager
    def tx(self) -> Iterator["Database"]:
        """A write transaction (re-entrant: nested calls join the outer transaction)."""
        with self.lock:
            outer = self._tx_depth == 0
            if outer:
                self.con.execute("BEGIN IMMEDIATE")
            self._tx_depth += 1
            try:
                yield self
            except BaseException:
                self._tx_depth -= 1
                if outer:
                    self.con.execute("ROLLBACK")
                raise
            else:
                self._tx_depth -= 1
                if outer:
                    self.con.execute("COMMIT")

    def script(self, sql: str) -> None:
        with self.lock:
            self.con.executescript(sql)

    def integrity_ok(self) -> bool:
        return self.scalar("PRAGMA integrity_check") == "ok"

    def close(self) -> None:
        with self.lock:
            self.con.close()


Writer = Callable[[Database], Any]
