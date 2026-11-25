"""TS-NFR13, TS-NFR07a (T-09): JSON lines with correlation id; canary secrets redacted (known-answer)."""
import io
import json
import logging

import pytest

from newsmon.obs import logging as obslog

pytestmark = pytest.mark.unit
CANARY = "sk-canary-0123456789abcdef"


@pytest.mark.req("NFR-13")
def test_one_json_line_per_record():
    buf = io.StringIO()
    obslog.setup([], stream=buf)
    cid = obslog.new_correlation_id("cycle")
    obslog.event("fetch_done", source="bbc_world", stage="collect", status="ok", entries=3)
    obslog.event("fetch_failed", logging.WARNING, source="x", stage="collect", error_class="timeout")
    lines = buf.getvalue().strip().splitlines()
    assert len(lines) == 2
    rec = [json.loads(x) for x in lines]
    assert rec[0]["event"] == "fetch_done" and rec[0]["correlation_id"] == cid and rec[0]["ts"]
    assert rec[1]["level"] == "warning" and rec[1]["error_class"] == "timeout" and rec[1]["source"] == "x"


@pytest.mark.req("NFR-07")
def test_canary_redacted_in_message_fields_and_exception():
    buf = io.StringIO()
    obslog.setup([CANARY], stream=buf)
    log = logging.getLogger(obslog.LOGGER_NAME)
    log.info("key is %s", CANARY)
    obslog.event("x", detail=f"Bearer {CANARY}", nested={"k": [CANARY]})
    try:
        raise RuntimeError(f"auth failed for {CANARY}")
    except RuntimeError:
        log.exception("boom")
    out = buf.getvalue()
    assert CANARY not in out
    assert out.count("[REDACTED]") >= 4


def test_redaction_control_without_secret():
    buf = io.StringIO()
    obslog.setup([], stream=buf)
    obslog.event("x", detail=CANARY)
    assert CANARY in buf.getvalue()  # the filter is what removes it, not the formatter
