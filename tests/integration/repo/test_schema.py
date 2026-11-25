"""TS-DB-01 (T-07): migrate creates every table; integrity ok; FTS5 contentless_delete accepted; portable types only."""
import re
from importlib import resources

import pytest

from newsmon.repo.db import Database
from newsmon.repo.migrate import _migrations, current_version, migrate, pending

pytestmark = pytest.mark.integration

EXPECTED = {"workspace", "source", "feed", "fetch_run", "inbox_ledger", "quarantine", "article", "article_revision",
            "feed_entry", "near_dup_link", "media_asset", "event", "event_member", "article_embedding",
            "ai_interpretation", "claim", "entity", "entity_mention", "editorial_assessment", "profile", "rule_hit",
            "alert", "incident", "source_health", "digest", "digest_item", "outbox", "delivery_log", "app_user",
            "api_token", "audit_log", "spend_day", "search_fts", "schema_version", "app_state"}


@pytest.mark.req("NFR-22")
def test_migrate_creates_every_table(db):
    names = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert EXPECTED <= names, EXPECTED - names
    assert db.integrity_ok()
    assert current_version(db) == len(_migrations()) and pending(db) == []
    assert db.scalar("PRAGMA journal_mode") == "wal"
    assert db.scalar("PRAGMA foreign_keys") == 1


def test_migrate_is_idempotent(tmp_path):
    d = Database(tmp_path / "x.sqlite")
    assert migrate(d) == [m[1] for m in _migrations()] and migrate(d)[:0] == []
    assert migrate(d) == []
    d.close()


@pytest.mark.req("NFR-22")
def test_fts5_contentless_delete(db):
    db.execute("INSERT INTO search_fts (rowid, headline_tok, text_tok, ai_tok, entity_tok) VALUES (7, 'a b', '', '', '')")
    assert db.scalar("SELECT rowid FROM search_fts WHERE search_fts MATCH 'b'") == 7
    db.execute("DELETE FROM search_fts WHERE rowid = 7")  # needs contentless_delete=1 (OQ-9)
    assert db.scalar("SELECT count(*) FROM search_fts WHERE search_fts MATCH 'b'") == 0


@pytest.mark.req("NFR-22")
def test_ddl_uses_only_portable_types():
    sql = resources.files("newsmon.repo").joinpath("migrations/0001_initial.sql").read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)
    types = set()
    for body in re.findall(r"CREATE TABLE \w+ \((.*?)\);", sql, re.S):
        for col in re.split(r",(?![^()]*\))", body):
            tok = col.split()
            if len(tok) >= 2 and tok[0].isidentifier() and tok[0].upper() not in ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN"):
                types.add(tok[1].upper())
    assert types and types <= {"INTEGER", "REAL", "TEXT", "BLOB"}, types
