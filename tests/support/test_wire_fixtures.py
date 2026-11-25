"""TS-FIX-03: the synthetic wire fixtures (T-06, ADR-010 §8) are complete, marked and well-formed."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree.ElementTree import ParseError

import defusedxml
import defusedxml.ElementTree as DET
import pytest
import yaml

from tests.support.wire_recipes import INBOX_DIR, WIRE_DIR, copy_inbox, make_oversize, make_symlink_escape

pytestmark = pytest.mark.support

GOLDEN_DIR = WIRE_DIR / "golden"
BAD_DIR = WIRE_DIR / "bad"
XML_MARK = "<!-- SYNTHETIC FIXTURE: project-made text, not agency copy -->"
FORMATS = ("newsml_g2", "nitf", "ninjs", "plain")
MIN_ITEMS = {"newsml_g2": 5, "nitf": 3, "ninjs": 5, "plain": 5}
ITEM_KEYS = {
    "uri", "version", "type", "headline", "slugline", "located", "language", "urgency", "versioncreated",
    "firstcreated", "pubstatus", "description_text", "body_text", "associations", "renditions", "restrictions",
    "media_refs",
}
AP_NAME = re.compile(r"^[0-9A-Za-z]+--\d+--[0-9A-Za-z]+\.[a-z0-9]+$")
UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
UN_HEADLINE = "UN Security Council schedules emergency session on Sudan ceasefire"
UN_P1 = ("The UN Security Council will hold an emergency session on Thursday to discuss the collapsing ceasefire in "
         "Sudan, diplomats said, after renewed fighting around El Fasher killed dozens of civilians.")


def _rel(p: Path, base: Path) -> str:
    return p.relative_to(base).as_posix()


def _inbox_files() -> list[Path]:
    return sorted(p for p in INBOX_DIR.rglob("*") if p.is_file())


def _golden() -> dict[str, dict]:
    """inbox-relative path -> golden document."""
    out = {}
    for g in sorted(GOLDEN_DIR.rglob("*.json")):
        out[_rel(g, GOLDEN_DIR)[: -len(".json")]] = json.loads(g.read_text("utf-8"))
    return out


def _items(fmt: str) -> list[tuple[str, dict]]:
    return [(rel, it) for rel, doc in _golden().items() if doc["format"] == fmt for it in doc["items"]]


def _manifest() -> dict:
    return json.loads((WIRE_DIR / "manifest.json").read_text("utf-8"))


# ---------------------------------------------------------------- inventory


def test_inbox_has_at_least_18_files():
    assert len(_inbox_files()) >= 18


def test_every_valid_inbox_file_has_golden_and_vice_versa():
    inbox = {_rel(p, INBOX_DIR) for p in _inbox_files() if p.suffix != ".mp4"}
    golden = set(_golden())
    assert inbox == golden, f"missing golden: {inbox - golden}; orphan golden: {golden - inbox}"


def test_golden_shape_and_format_matches_folder():
    for rel, doc in _golden().items():
        assert doc["synthetic"] is True, rel
        assert doc["format"] == rel.split("/")[0], rel
        assert doc["items"], rel
        for it in doc["items"]:
            assert set(it) == ITEM_KEYS, (rel, set(it) ^ ITEM_KEYS)
            assert isinstance(it["version"], int) and it["version"] >= 1, rel
            assert UTC_Z.match(it["versioncreated"]), rel
            assert it["firstcreated"] is None or UTC_Z.match(it["firstcreated"]), rel
            assert it["pubstatus"] in {"usable", "withheld", "canceled"}, rel
            assert it["urgency"] is None or 1 <= it["urgency"] <= 8, rel
            assert re.fullmatch(r"[a-z]{2,3}", it["language"]), rel
            assert isinstance(it["associations"], dict) and isinstance(it["renditions"], list), rel
            assert isinstance(it["media_refs"], list), rel


@pytest.mark.parametrize("fmt", FORMATS)
def test_minimum_item_count_per_format(fmt):
    assert len(_items(fmt)) >= MIN_ITEMS[fmt]


# ---------------------------------------------------------------- must-include cases


def test_g2_version_update_of_same_guid():
    m = _manifest()["g2_version_pair"]
    g = _golden()
    v1, v2 = g[m["v1"]]["items"][0], g[m["v2"]]["items"][0]
    assert m["v1"] != m["v2"]
    assert v1["uri"] == v2["uri"]
    assert (v1["version"], v2["version"]) == (1, 2)
    assert v1["headline"] != v2["headline"] and v1["body_text"] != v2["body_text"]
    assert v2["versioncreated"] > v1["versioncreated"]


def test_g2_kill_cancels_an_earlier_item():
    m = _manifest()["g2_kill"]
    g = _golden()
    kill = g[m["kill"]]["items"][0]
    assert kill["pubstatus"] == "canceled"
    earlier = [it for it in g[m["killed"]]["items"] if it["uri"] == kill["uri"]]
    assert earlier and earlier[0]["pubstatus"] == "usable"
    assert earlier[0]["version"] < kill["version"]
    assert 'qcode="stat:canceled"' in (INBOX_DIR / m["kill"]).read_text("utf-8")


def test_nitf_shotlist_association():
    rel = _manifest()["nitf_shotlist"]
    it = _golden()[rel]["items"][0]
    shots = it["associations"]["shotlist"].split("\n")
    assert len(shots) >= 3 and all(re.match(r"^\d+\. ", s) for s in shots)
    assert it["body_text"] and "shotlist" not in it["body_text"].lower()
    assert 'class="shotlist"' in (INBOX_DIR / rel).read_text("utf-8")


def test_ninjs_video_with_rendition_and_ap_style_name():
    m = _manifest()["ninjs_video"]
    side, media = INBOX_DIR / m["sidecar"], INBOX_DIR / m["media"]
    assert AP_NAME.match(side.name) and AP_NAME.match(media.name)
    item_id, version, _ = side.stem.split("--")
    it = _golden()[m["sidecar"]]["items"][0]
    assert it["type"] == "video"
    assert it["uri"] == item_id and it["version"] == int(version)
    r = it["renditions"][0]
    assert r["href"] == media.name and r["contenttype"] == "video/mp4"
    assert {"duration", "width", "height", "sizeinbytes"} <= set(r)
    assert r["sizeinbytes"] == media.stat().st_size
    assert it["media_refs"] == [media.name]
    # FR-31(a): the golden renditions equal the source renditions verbatim.
    assert json.loads(side.read_text("utf-8"))["renditions"] == it["renditions"]


def test_ninjs_unknown_restriction():
    rel = _manifest()["ninjs_unknown_restriction"]
    assert _golden()[rel]["items"][0]["restrictions"] == "ZZ-UNKNOWN-RESTRICTION"


def test_fake_mp4_starts_with_ftyp_box():
    mp4s = list(INBOX_DIR.rglob("*.mp4"))
    assert len(mp4s) == 1
    data = mp4s[0].read_bytes()
    assert 1024 <= len(data) <= 4096
    assert data[4:8] == b"ftyp" and data[8:12] == b"isom"


def test_plain_flash_and_korean():
    items = _items("plain")
    assert any(it["urgency"] == 1 for _, it in items)
    ko = [it for _, it in items if it["language"] == "ko"]
    assert ko and re.search(r"[가-힣]", ko[0]["headline"]) and re.search(r"[가-힣]", ko[0]["body_text"])
    m = _manifest()
    assert "URGENCY: 1\n" in (INBOX_DIR / m["plain_flash"]).read_text("utf-8")
    assert "LANGUAGE: ko\n" in (INBOX_DIR / m["plain_korean"]).read_text("utf-8")


def test_cross_format_near_duplicate_pair():
    g = _golden()
    for a, b in _manifest()["cross_format_pairs"]:
        ia, ib = g[a]["items"][0], g[b]["items"][0]
        assert g[a]["format"] != g[b]["format"]
        assert ia["uri"] != ib["uri"] and ia["body_text"] != ib["body_text"]
        ta = set(re.findall(r"\w+", (ia["headline"] + " " + ia["body_text"]).lower()))
        tb = set(re.findall(r"\w+", (ib["headline"] + " " + ib["body_text"]).lower()))
        assert len(ta & tb) / len(ta | tb) >= 0.5, "pair should be near-duplicates"


def test_un_sudan_cross_channel_story():
    rel = _manifest()["cross_channel_un_sudan"]
    it = _golden()[rel]["items"][0]
    assert it["headline"] == UN_HEADLINE
    assert it["body_text"].split("\n\n")[0] == UN_P1
    assert it["language"] == "en" and it["urgency"] == 3
    text = (INBOX_DIR / rel).read_text("utf-8")
    assert f"HEADLINE: {UN_HEADLINE}\n" in text and UN_P1 in text


# ---------------------------------------------------------------- markers


def _has_marker(p: Path) -> bool:
    if p.suffix == ".mp4":
        return b"SYNTHETIC FIXTURE" in p.read_bytes()
    text = p.read_text("utf-8")
    if p.suffix == ".xml":
        return XML_MARK in text
    if p.suffix == ".json":
        return json.loads(text).get("x_synthetic") is True
    if p.suffix == ".txt":
        return "SYNTHETIC: true" in text.splitlines()
    if p.suffix == ".yaml":
        return "SYNTHETIC FIXTURE" in text and all(s.get("synthetic") is True for s in yaml.safe_load(text)["sources"])
    return False


def test_every_file_carries_synthetic_marker():
    unmarked = []
    for p in sorted(WIRE_DIR.rglob("*")):
        if not p.is_file() or p.name in {"README.md", "FORMAT.md"} or GOLDEN_DIR in p.parents:
            continue
        if BAD_DIR in p.parents:
            ok = p.name.startswith("synthetic_") and ("SYNTHETIC" in p.read_text("utf-8", errors="replace")
                                                      or "x_synthetic" in p.read_text("utf-8", errors="replace"))
        else:
            ok = _has_marker(p)
        if not ok:
            unmarked.append(_rel(p, WIRE_DIR))
    assert not unmarked, unmarked


def test_no_symlinks_or_oversize_files_committed():
    for p in WIRE_DIR.rglob("*"):
        assert not p.is_symlink(), p
        if p.is_file():
            assert p.stat().st_size < 64 * 1024, p


# ---------------------------------------------------------------- bad files and well-formedness


def test_bad_files_cover_each_format_and_attacks():
    kinds = Counter(_rel(p, BAD_DIR).split("/")[0] for p in BAD_DIR.rglob("*") if p.is_file())
    for k in (*FORMATS, "unknown"):
        assert kinds[k] >= 1, k
    names = {p.name for p in (BAD_DIR / "security").iterdir()}
    assert any("xxe" in n for n in names) and any("billion_laughs" in n for n in names)


@pytest.mark.parametrize("fmt", ["newsml_g2", "nitf"])
def test_malformed_xml_fails_to_parse(fmt):
    for p in (BAD_DIR / fmt).glob("*.xml"):
        with pytest.raises(ParseError):
            DET.fromstring(p.read_bytes())


def test_malformed_ninjs_is_invalid_json():
    for p in (BAD_DIR / "ninjs").glob("*.json"):
        with pytest.raises(json.JSONDecodeError):
            json.loads(p.read_text("utf-8"))


def test_malformed_plain_lacks_headline():
    for p in (BAD_DIR / "plain").glob("*.txt"):
        header = p.read_text("utf-8").split("\nBODY:\n", 1)[0]
        assert "SYNTHETIC: true" in header
        assert not any(line.startswith("HEADLINE:") for line in header.splitlines())


@pytest.mark.parametrize("name", ["synthetic_xxe_g2.xml", "synthetic_billion_laughs_g2.xml"])
def test_attack_xml_raises_in_defusedxml(name):
    data = (BAD_DIR / "security" / name).read_bytes()
    with pytest.raises(defusedxml.DefusedXmlException):
        DET.fromstring(data)


def test_valid_xml_is_well_formed_under_defusedxml():
    xml_files = [p for p in _inbox_files() if p.suffix == ".xml"]
    assert len(xml_files) >= 9
    for p in xml_files:
        DET.fromstring(p.read_bytes())


def test_valid_json_parses():
    for p in _inbox_files():
        if p.suffix == ".json":
            assert isinstance(json.loads(p.read_text("utf-8")), dict), p
    assert isinstance(_manifest(), dict)


def test_sources_mock_rows():
    rows = {s["key"]: s for s in yaml.safe_load((WIRE_DIR / "sources_mock.yaml").read_text("utf-8"))["sources"]}
    gated, demo = rows["mock_wire_gated"], rows["mock_wire_demo"]
    assert gated["permitted_ops"] == [] and gated["external_ai_allowed"] is False
    assert gated["redistribution"] == "none" and gated["retention_days"] == 7
    assert demo["permitted_ops"] == ["classify", "summarise", "translate", "embed"]
    assert demo["external_ai_allowed"] is True and demo["retention_days"] == 30
    for s in rows.values():
        assert s["access_method"] == "directory" and s["is_wire"] is True and s["synthetic"] is True


def test_uris_unique_per_version():
    seen = defaultdict(list)
    for rel, doc in _golden().items():
        for it in doc["items"]:
            seen[(it["uri"], it["version"])].append(rel)
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dupes, dupes


# ---------------------------------------------------------------- recipes


def test_make_oversize_writes_requested_size(tmp_path):
    size = 3 * 1024 * 1024 + 17
    p = make_oversize(tmp_path / "big.txt", size)
    assert p.stat().st_size == size
    head = p.read_bytes()[:400].decode("ascii")
    assert head.startswith("SYNTHETIC: true\n") and "\nHEADLINE: " in head and "\nBODY:\n" in head


def test_make_symlink_escape_returns_path_or_none(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    root = tmp_path / "root"
    link = make_symlink_escape(root, outside)
    if link is None:
        pytest.skip("OS refused to create a symlink (e.g. Windows without developer mode)")
    assert isinstance(link, Path) and link.is_symlink()
    assert root in link.parents
    assert root.resolve() not in link.resolve().parents


def test_copy_inbox_copies_everything(tmp_path):
    copies = copy_inbox(tmp_path / "inbox")
    assert len(copies) == len(_inbox_files())
    assert {_rel(c, tmp_path / "inbox") for c in copies} == {_rel(p, INBOX_DIR) for p in _inbox_files()}
    assert any(c.suffix == ".mp4" for c in copies)
