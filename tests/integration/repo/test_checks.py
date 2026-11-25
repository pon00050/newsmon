"""TS-FR01d, TS-FR30a-db (T-07)."""
import sqlite3

import pytest

pytestmark = pytest.mark.integration
NOW = "2026-11-25T00:00:00+00:00"
COLS = ("key", "name", "access_method", "created_utc", "training", "licence_owner", "retention_days", "active")


def _insert(db, key, training="no", licence_owner="unknown", retention_days=None, active=1):
    db.execute("INSERT INTO source (key, name, access_method, created_utc, training, licence_owner, retention_days, active) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (key, "n", "directory", NOW, training, licence_owner, retention_days, active))


@pytest.mark.req("FR-01d")
def test_training_fixed(db):
    with pytest.raises(sqlite3.IntegrityError):
        _insert(db, "bad", training="yes")
    _insert(db, "ok")
    assert db.scalar("SELECT training FROM source WHERE key = 'ok'") == "no"


@pytest.mark.req("FR-30a")
def test_tenant_needs_attestation(db):
    with pytest.raises(sqlite3.IntegrityError):  # no retention_days
        _insert(db, "t1", licence_owner="tenant", active=0)
    with pytest.raises(sqlite3.IntegrityError):  # active without attestation
        _insert(db, "t2", licence_owner="tenant", retention_days=7, active=1)
    _insert(db, "t3", licence_owner="tenant", retention_days=7, active=0)
    with pytest.raises(sqlite3.IntegrityError):  # activating later without attestation
        db.execute("UPDATE source SET active = 1 WHERE key = 't3'")
    db.execute("UPDATE source SET attested_on = '2026-11-25', attested_by = 'admin', active = 1 WHERE key = 't3'")
    assert db.scalar("SELECT active FROM source WHERE key = 't3'") == 1
