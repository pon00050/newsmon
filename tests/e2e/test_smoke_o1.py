"""TS-E2E-00 (T-08): init + one cycle on fixture feeds and the synthetic inbox, with the network guarded and no AI.

articles > 0; netguard sees 0 non-loopback connects (the autouse guard fails the test otherwise); the AI keys are
unset; the queue query returns rows with a headline and a band.
"""
import os

import pytest

from newsmon.adapters.null_ai import AI_OFF
from newsmon.cli import main
from tests.support.instance import feed_source, fill_inbox, make_app, mock_wire_sources, serve_feeds

pytestmark = pytest.mark.e2e


@pytest.mark.req("AC-O1-01", "RA-02", "RA-03")
def test_smoke_o1(tmp_path, fixture_server, netguard):
    assert "ANTHROPIC_API_KEY" not in os.environ and "OPENAI_API_KEY" not in os.environ
    urls = serve_feeds(fixture_server, ["bbc_world.xml", "yna_nk.xml", "rfi_zh.xml"])
    sources = [feed_source("bbc_world", urls["bbc_world.xml"]), feed_source("yna_nk", urls["yna_nk.xml"], "ko"),
               feed_source("rfi_zh", urls["rfi_zh.xml"], "zh")] + mock_wire_sources()
    app = make_app(tmp_path, fixture_server, sources, with_inbox=True)
    try:
        assert app.ai_status.header_label() == AI_OFF
        fill_inbox(app)
        first = app.collect(force=True)
        assert not first.failed, [(f.source_key, f.error_class, f.detail) for f in first.failed]
        second = app.collect(force=True)  # inbox files are stable now and get ingested
        counts = app.articles.counts()
        assert counts["articles"] > 20, counts
        queue = app.articles.queue(limit=500)
        assert queue and all(r["headline"] and r["final_band"] for r in queue)
        assert any(r["source_key"] == "mock_wire_demo" for r in queue)
        assert second.new_articles > 0
    finally:
        app.close()
    assert netguard.violations == []


def test_cli_init_and_collect_offline(tmp_path, monkeypatch, capsys):
    """`newsmon init` + `newsmon collect` with only a directory source: no network at all."""
    from tests.support.instance import write_config
    cfg = write_config(tmp_path / "cfg", mock_wire_sources())
    for k in ("mock_wire_gated", "mock_wire_demo"):
        (cfg / "inbox" / k).mkdir(parents=True)
    monkeypatch.setenv("NEWSMON_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("NEWSMON_DATA_DIR", str(tmp_path / "data"))
    assert main(["init"]) == 0
    assert (tmp_path / "data" / "newsmon.sqlite").exists()
    from tests.support.wire_recipes import copy_inbox
    copy_inbox(cfg / "inbox" / "mock_wire_demo")
    assert main(["collect"]) == 0
    assert main(["collect", "--force"]) == 0
    out = capsys.readouterr().out
    assert "mock_wire_demo" in out
    assert main(["status"]) == 0
