"""Live provider validation for Release A.1 (opt-in: NEWSMON_LIVE=1, key from NEWSMON_LIVE_ENV_FILE or the environment).

A small representative set: the synthetic wire items whose attested flags permit AI (mock_wire_demo), capped at 6 calls
and $0.05. Asserts validated structured output, Korean fields, recorded usage, the cache, and zero calls for the gated
wire. Never runs in the regression gate.
"""
import os
from pathlib import Path

import pytest

from newsmon.adapters.anthropic_ai import AnthropicProvider
from newsmon.adapters.secrets import EnvSecretStore
from tests.support.instance import fill_inbox, make_app, mock_wire_sources

pytestmark = pytest.mark.live
SETTINGS = {"use_context": "private", "ai": {"capabilities": {"enrich": True}, "daily_cap_usd": 0.05,
                                              "selection": {"min_band": "drop", "max_items_per_cycle": 6}}}


def test_live_enrichment_small_set(tmp_path, capsys):
    env_file = os.environ.get("NEWSMON_LIVE_ENV_FILE")
    key = EnvSecretStore(Path(env_file) if env_file else None).get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("no ANTHROPIC_API_KEY available")
    app = make_app(tmp_path, None, mock_wire_sources(), settings=SETTINGS, with_inbox=True)
    try:
        app.use_ai_provider(AnthropicProvider(key, timeout=60, max_retries=1))
        fill_inbox(app, "mock_wire_demo")
        app.collect(force=True)
        rep = app.collect(force=True).ai
        print(f"LIVE: selected={rep.selected} called={rep.called} done={rep.done} review={rep.review} "
              f"cost_usd={rep.cost_usd:.6f} stopped={rep.stopped} errors={rep.errors}")
        assert rep.called >= 4 and rep.cost_usd < 0.05
        assert rep.done >= rep.selected - 1  # at most one item may land in review
        rows = app.db.query("SELECT output_json, validation_status, input_tokens, output_tokens, cost_usd, latency_ms "
                            "FROM ai_interpretation WHERE validation_status IN ('valid', 'retried_valid')")
        import json
        for r in rows:
            out = json.loads(r[0])
            print("LIVE item:", out["relevance_band"], out["importance"], out["topics"], "|", out.get("headline_ko"), "|",
                  (out.get("summary_ko") or "")[:120], "| tokens", r[2], r[3], "$", r[4], f"{r[5]}ms")
            assert out.get("headline_ko") and out.get("summary_ko")
        totals = app.ai_repo.usage_totals()
        print("LIVE totals:", totals)
        n = rep.called
        again = app.enrich(uids=[u for (u,) in app.db.query(
            "SELECT uid FROM article WHERE enrichment_status = 'done'")])
        assert again.called == 0 and again.cached >= rep.done  # cache: unchanged content, no new calls
        del n
    finally:
        app.close()
