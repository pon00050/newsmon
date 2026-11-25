"""Wire parsers (T-34): FR-29(a) golden equality, (b) shotlist association, (c) malformed quarantined, (d) XXE refused."""
import json
from pathlib import Path

import pytest

from newsmon.connectors.wire import WireParseError, detect_format, parse_wire

pytestmark = pytest.mark.unit
WIRE = Path(__file__).resolve().parents[2] / "fixtures" / "wire"
VALID = sorted(p for p in (WIRE / "inbox").rglob("*") if p.is_file() and p.suffix != ".mp4")


@pytest.mark.req("FR-29a", "RA-05")
@pytest.mark.parametrize("path", VALID, ids=lambda p: p.name)
def test_golden_field_equality(path):
    golden = json.loads((WIRE / "golden" / (path.relative_to(WIRE / "inbox").as_posix() + ".json")).read_text("utf-8"))
    fmt, items = parse_wire(path.read_bytes())
    assert fmt == golden["format"]
    assert len(items) == len(golden["items"])
    for got, want in zip(items, golden["items"]):
        for field, value in want.items():
            assert got[field] == value, (path.name, field, got[field], value)


@pytest.mark.req("FR-29b")
def test_shotlist_is_an_association():
    _, items = parse_wire((WIRE / "inbox" / "nitf" / "nitf_0003_kenya_sorghum_video_script.xml").read_bytes())
    assert items[0]["associations"]["shotlist"].startswith("1. Wide of dry maize field")
    assert "Wide of dry maize" not in (items[0]["body_text"] or "")


@pytest.mark.req("FR-29c")
@pytest.mark.parametrize("path", sorted(p for p in (WIRE / "bad").rglob("*") if p.is_file()), ids=lambda p: p.name)
def test_bad_files_raise(path):
    with pytest.raises(WireParseError):
        parse_wire(path.read_bytes())


@pytest.mark.req("FR-29d")
def test_xxe_and_billion_laughs_refused(tmp_path, monkeypatch):
    opened = []
    import builtins
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])
    for name in ("synthetic_xxe_g2.xml", "synthetic_billion_laughs_g2.xml"):
        data = (WIRE / "bad" / "security" / name).read_bytes()
        with pytest.raises(WireParseError, match="unsafe XML refused"):
            parse_wire(data)
    assert not any("win.ini" in f for f in opened)


def test_detection_by_content_not_extension():
    data = (WIRE / "inbox" / "plain" / "ptw_0001_taiwan_quake_flash.txt").read_bytes()
    assert detect_format(data) == "plain"
    assert detect_format((WIRE / "inbox" / "ninjs" / "a1b2c3d4e5f6--2--0c4d2e7a.mp4").read_bytes()) == "media"
    assert detect_format(b"a,b,c\n1,2,3\n") == "unknown"
