import pytest

from newsmon.repo.db import Database
from newsmon.repo.migrate import ensure_workspace, migrate


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "t.sqlite")
    migrate(d)
    ensure_workspace(d, "test", "private", "2026-11-25T00:00:00+00:00")
    yield d
    d.close()
