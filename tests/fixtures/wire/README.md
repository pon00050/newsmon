# Synthetic wire fixtures (T-06, ADR-010 §8)

Every file here is **synthetic**: text written for the newsmon project about plausible foreign-news topics. None of
it is agency copy, and no name, figure or quote should be read as a real report. The point is to exercise the
directory watcher, format detection, the four wire parsers, licence gating and the end-to-end path without paid wire
access. Checked by `tests/support/test_wire_fixtures.py` (TS-FIX-03).

## Layout

```
wire/
  inbox/                 valid files, as a watched customer inbox would hold them (20 files)
    newsml_g2/           NewsML-G2 XML (bare newsItem or newsMessage/itemSet/newsItem)
    nitf/                NITF XML
    ninjs/               ninjs 2.x-style JSON, plus one fake .mp4 referenced by a ninjs video item
    plain/               project-defined plain-text wire (spec: plain/FORMAT.md)
  golden/                expected parser output, one JSON per inbox file: golden/<inbox relative path>.json
  bad/                   files that must be rejected or quarantined, never parsed into items
    newsml_g2/ nitf/ ninjs/ plain/   one malformed file per format
    security/            XXE and billion-laughs XML (must raise under defusedxml)
    unknown/             a CSV that matches no wire format
  plain/FORMAT.md        the plain-text wire format
  manifest.json          roles of specific files (version pair, kill, video, cross-format pair, ...)
  sources_mock.yaml      two mock source registrations (mock_wire_gated, mock_wire_demo)
```

The oversize file and the symlink-escape case are **not committed**; tests build them at run time with
`tests/support/wire_recipes.py` (`make_oversize`, `make_symlink_escape`). `copy_inbox(dst)` copies the whole inbox
(including the .mp4) into a temporary watched folder.

## Counts

| Format | Files | Items | Must-include cases |
|---|---|---|---|
| NewsML-G2 | 6 | 7 | gx-0001 at version 1 and version 2 (separate files, changed headline/body); gx-0003 killed by a version-2 `stat:canceled` item; one `newsMessage` with two items; one French item |
| NITF | 3 | 3 | `nitf_0003` is a video script with `<block class="story">` (body) and `<block class="shotlist">` (association) |
| ninjs | 5 (+1 .mp4) | 5 | `a1b2c3d4e5f6--2--f9e8d7c6.json` is `type: video` with a rendition pointing at `a1b2c3d4e5f6--2--0c4d2e7a.mp4` (AP-style `ItemID--Version--ContentID`; FR-31(a) round-trip); `ninjs_0004` has `restrictions: ZZ-UNKNOWN-RESTRICTION` (FR-31(b)); `ninjs_0005` is `withheld` and Spanish; `ninjs_0001` uses `en-GB` and irregular whitespace |
| Plain text | 5 | 5 | `URGENCY: 1` flash; Korean item (`LANGUAGE: ko`, +09:00 offset); UN Security Council / Sudan story for FR-27(a) |

Cross-format near-duplicate pair: `newsml_g2/g2_0004_peru_copper.xml` and `plain/ptw_0003_peru_copper.txt` (same facts,
different wording and wrapping).

## Synthetic markers

- XML: the comment `<!-- SYNTHETIC FIXTURE: project-made text, not agency copy -->` near the top.
- ninjs JSON and `manifest.json`: top-level `"x_synthetic": true`.
- Plain text: header line `SYNTHETIC: true`.
- The .mp4: a `free` box containing `SYNTHETIC FIXTURE`.
- Bad files: file names start with `synthetic_`, and carry the marker text where the format allows.
- Golden JSON: `"synthetic": true`.

## Golden JSON

```
{"format": "newsml_g2" | "nitf" | "ninjs" | "plain",
 "items": [ {uri, version, type, headline, slugline, located, language, urgency, versioncreated, firstcreated,
             pubstatus, description_text, body_text, associations, renditions, restrictions, media_refs} ],
 "synthetic": true}
```

Items are in document order. Field semantics, for field-level equality checks (FR-29(a)):

| Field | Rule |
|---|---|
| `uri` | G2 `newsItem@guid`; NITF `doc-id@id-string`; ninjs `uri`; plain `ID` |
| `version` | int. G2 `newsItem@version`; NITF `du-key@version`; ninjs `version` (a string in the file, as in ninjs 2.x); plain `VERSION` |
| `type` | G2 `itemClass@qcode` after `ninat:`; ninjs `type`; NITF and plain `text` (the NITF video **script** is a text item) |
| `headline` | G2 `headline`; NITF `hl1`; whitespace-collapsed |
| `slugline` | G2 `slugline`; NITF `du-key@key`; plain `SLUG` |
| `located` | G2 `located/name`; NITF `dateline/location/city`; ninjs `located`; plain `DATELINE` |
| `language` | primary BCP-47 subtag, lower case (`en-GB` gives `en`). G2 `language@tag`; NITF `nitf@baselang` |
| `urgency` | int or null. G2 `urgency`; NITF `urgency@ed-urg` |
| `versioncreated` | UTC, `YYYY-MM-DDTHH:MM:SSZ`, converted from the source offset. NITF uses `date.issue@norm` (ISO basic format) |
| `firstcreated` | same format, or null when absent (all NITF items) |
| `pubstatus` | `usable`/`withheld`/`canceled`. G2 `pubStatus@qcode` after `stat:`; NITF `docdata@management-status` |
| `description_text` | G2 `description[@role=drol:summary]`; NITF `abstract`; ninjs `description_text`; plain `DESCRIPTION`; else null |
| `body_text` | paragraphs (G2 XHTML `<p>`, NITF non-shotlist block `<p>`, ninjs/plain blank-line separated), each whitespace-collapsed and stripped, joined by `\n\n`; null when there is no body |
| `associations` | `{"shotlist": "<shot lines joined by \n>"}` for the NITF shotlist item; otherwise `{}` |
| `renditions` | ninjs `renditions`, verbatim; otherwise `[]` |
| `restrictions` | ninjs `restrictions` or plain `RESTRICTIONS`; else null |
| `media_refs` | file names referenced by renditions (`href`); otherwise `[]` |

The licence flags in `sources_mock.yaml` are synthetic examples, not a statement about any real contract.
