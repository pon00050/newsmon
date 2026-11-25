"""TS-NFR23a (T-07): root tables carry workspace_id NOT NULL; child tables reach a root by FK."""
import pytest

from newsmon.repo.base import CHILD_TABLES, ROOT_TABLES

pytestmark = pytest.mark.integration


@pytest.mark.req("NFR-23")
def test_root_tables_have_workspace_id_not_null(db):
    for t in ROOT_TABLES:
        cols = {r["name"]: r for r in db.query(f"PRAGMA table_info({t})")}
        assert "workspace_id" in cols, t
        assert cols["workspace_id"]["notnull"] == 1, t


@pytest.mark.req("NFR-23")
def test_every_table_is_root_or_child(db):
    tables = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")
              if not r[0].startswith(("sqlite_", "search_fts"))} - {"schema_version", "workspace"}
    declared = set(ROOT_TABLES) | set(CHILD_TABLES)
    assert tables == declared, tables ^ declared
    for child, parent in CHILD_TABLES.items():
        fks = {r["table"] for r in db.query(f"PRAGMA foreign_key_list({child})")}
        assert parent in fks, (child, parent, fks)
