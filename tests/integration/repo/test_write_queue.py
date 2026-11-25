"""TS-DB-02 (T-07): 20 concurrent writers produce no 'database is locked' and every row lands."""
import threading

import pytest

pytestmark = pytest.mark.integration


def test_concurrent_writers(db):
    errors = []

    def writer(i):
        try:
            for j in range(25):
                with db.tx():
                    db.execute("INSERT INTO audit_log (at_utc, actor, action, target) VALUES (?, ?, ?, ?)",
                               ("2026-11-25T00:00:00+00:00", f"w{i}", "test", str(j)))
        except Exception as exc:  # reported below
            errors.append(repr(exc))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert db.scalar("SELECT count(*) FROM audit_log WHERE action = 'test'") == 500


def test_tx_rolls_back(db):
    with pytest.raises(RuntimeError):
        with db.tx():
            db.execute("INSERT INTO audit_log (at_utc, actor, action) VALUES ('t', 'a', 'x')")
            raise RuntimeError
    assert db.scalar("SELECT count(*) FROM audit_log WHERE action = 'x'") == 0
