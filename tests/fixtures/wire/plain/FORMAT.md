# Plain-text wire format (project-defined, synthetic)

This is a mock format made for the newsmon project (ADR-010 §3, "Text with a header block"). It is not any agency's
format. Fixtures in `inbox/plain/` follow it.

## File

- Extension `.txt`. Encoding UTF-8 without BOM. Line endings LF (a parser should also accept CRLF).
- One item per file.

## Header block

The file starts with `KEY: value` lines, one per line. The key is upper case ASCII; the value is everything after the
**first** `:` with surrounding whitespace stripped (so `HEADLINE: FLASH: Strong earthquake ...` has the value
`FLASH: Strong earthquake ...`). Unknown keys are ignored. Key order is free.

| Key | Required | Value | Maps to |
|---|---|---|---|
| `SYNTHETIC` | fixtures only | `true` marks a project-made file | provenance `synthetic` |
| `ID` | yes | source's own id | `uri` |
| `VERSION` | yes | positive integer | `version` |
| `VERSIONCREATED` | yes | ISO 8601 with an offset (`2026-11-24T10:05:00+09:00`) | `versioncreated`, converted to UTC |
| `FIRSTCREATED` | no | ISO 8601 with an offset | `firstcreated` (UTC), else null |
| `LANGUAGE` | yes | BCP-47 tag (`en`, `ko`, `en-GB`) | `language` (primary subtag, lower case) |
| `URGENCY` | yes | integer 1 (flash) to 8 (lowest) | `urgency` |
| `SLUG` | yes | slug text | `slugline` |
| `HEADLINE` | yes | headline text | `headline` |
| `DATELINE` | yes | place only, no date (`MANILA, Philippines`) | `located`, verbatim |
| `PUBSTATUS` | no | `usable` (default), `withheld` or `canceled` | `pubstatus` |
| `TYPE` | no | `text` (default) | `type` |
| `DESCRIPTION` | no | one-line summary | `description_text`, else null |
| `RESTRICTIONS` | no | free text | `restrictions`, else null |

A file missing any required key is malformed and must be quarantined (see `bad/plain/`).

## Body

- A line consisting of exactly `BODY:` ends the header block.
- Everything after it is the body. Paragraphs are separated by one or more blank lines.
- Lines inside a paragraph may be hard-wrapped; a parser joins them. Each paragraph is whitespace-collapsed
  (runs of whitespace become one space) and stripped; paragraphs are joined with `\n\n` to give `body_text`.
- An empty body gives `body_text = null`.

## Example

```
SYNTHETIC: true
ID: PTW-20261124-0001
VERSION: 1
VERSIONCREATED: 2026-11-24T22:47:00+08:00
LANGUAGE: en
URGENCY: 1
SLUG: TAIWAN-QUAKE
HEADLINE: FLASH: Strong earthquake strikes off east coast of Taiwan
DATELINE: TAIPEI, Taiwan
BODY:
A strong earthquake struck off the east coast of Taiwan on Tuesday night, the
island's weather agency said. More to follow.
```
