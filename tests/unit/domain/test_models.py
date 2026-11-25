"""Domain models and null adapters (T-03)."""
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from newsmon.adapters.null_ai import AI_OFF, NullAIProvider, NullAIStatus
from newsmon.domain.enums import AIOp, Band, Display, PollStatus, ErrorClass
from newsmon.domain.models import LicenceFlags, NormalisedItem, PollResult
from newsmon.domain.ports import AIProvider, AIStatus, AIUnavailable, Clock, SystemClock

pytestmark = pytest.mark.unit


@pytest.mark.req("FR-01")
def test_licence_flag_defaults_are_the_safety_choice():
    f = LicenceFlags()
    assert (f.storage, f.display, f.ai_processing, f.external_ai_allowed, f.permitted_ops, f.redistribution, f.training) == (
        "metadata", "headline", "unknown", False, frozenset(), "none", "no")


@pytest.mark.req("NFR-19")
def test_training_cannot_be_anything_but_no():
    with pytest.raises(ValidationError):
        LicenceFlags(training="yes")


def test_snapshot_is_stable_json():
    a = LicenceFlags(permitted_ops={AIOp.TRANSLATE, AIOp.CLASSIFY})
    b = LicenceFlags(permitted_ops={AIOp.CLASSIFY, AIOp.TRANSLATE})
    assert a.snapshot_json() == b.snapshot_json()
    assert json.loads(a.snapshot_json())["permitted_ops"] == ["classify", "translate"]


def test_band_and_display_order():
    assert Band.FLASH.rank > Band.REPORT.rank > Band.REVIEW.rank > Band.DROP.rank
    assert Display.FULL.rank > Display.SNIPPET.rank > Display.HEADLINE.rank > Display.NONE.rank


def test_poll_result_label():
    assert PollResult(status=PollStatus.ERROR, error_class=ErrorClass.SSRF_BLOCKED).label == "error:ssrf_blocked"
    assert PollResult(status=PollStatus.EMPTY).label == "empty"


def test_normalised_item_requires_provenance():
    with pytest.raises(ValidationError):
        NormalisedItem(headline="x")
    now = datetime.now(timezone.utc)
    item = NormalisedItem(headline="x", source_key="s", connector_kind="feed", raw_ref="u", raw_sha256="0" * 64,
                          parser="feedparser", received_utc=now, licence_snapshot=LicenceFlags().snapshot_json())
    assert item.synthetic is False and item.type == "text"


@pytest.mark.req("FR-15")
def test_null_ai_is_o1():
    p = NullAIProvider()
    assert isinstance(p, AIProvider) and isinstance(NullAIStatus(), AIStatus)
    assert NullAIStatus().header_label() == AI_OFF == "AI: 꺼짐"
    with pytest.raises(AIUnavailable):
        p.complete_json(task="triage", system="", user="", schema={}, model="m", fields_sent=[])
    with pytest.raises(AIUnavailable):
        p.embed(["x"], model="m")


def test_system_clock_is_utc():
    c = SystemClock()
    assert isinstance(c, Clock)
    assert c.now().tzinfo is not None and c.now().utcoffset().total_seconds() == 0
