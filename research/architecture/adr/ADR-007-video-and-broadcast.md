# ADR-007 · Video and broadcast (D7): deferred; the MVP is video-ready in schema and accepts text that rides with video

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: Deferred as decided; nothing to build.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Informs:** deliverable 11 §5 (item schema), ADR-010 (directory watcher), deliverable 09 (W3, W4 rows).

## Context

- About half of the 외신 seat's duty lines involve footage, ingest, archive or feed health (`01_INDUSTRY…` F-A-01).
- The tested technology is cheap and works: ffprobe, thumbnail strip, PySceneDetect, black/freeze/silence detectors (3/3
  injected faults fired, 0/12 false fires), Groq Whisper at about $0.0007/min on clean English (TESTED,
  [`experiments/multimedia/results.md`](../../experiments/multimedia/results.md)).
- The blocker is access, not technology: the only video the seat handles is licensed wire video and the broadcaster's own
  feeds (`07_MULTIMEDIA…` §1).
- YouTube: channel RSS is robots-disallowed (ADR-002); API policies forbid storing audiovisual content (DR-10).
- An open-standard video item carries headline, place, date, text shotlist, script, usage terms and renditions (NewsML-G2
  quickstart and ninjs user guide, VERIFIED, `07_MULTIMEDIA…` §2). AP/Reuters field lists are UNVERIFIED-absent.
- Supplement 02: a customer's AP Media Agent writes downloaded content (including footage and metadata) to a local
  directory; the MVP must handle representative local files through a generic interface.

## Options considered

1. Video in the MVP (ingest, ASR, scene detection, feed monitor).
2. **Defer video processing; make the schema and the directory watcher video-aware** (store sidecar metadata and a
   reference to the media file, never process or copy the media).
3. Ignore video entirely.

## Decision

**Option 2.**
- The item schema uses **ninjs field names** for `type` (text / video / audio / picture), `slugline`, `located`,
  `urgency`, `usageterms`, `subjects`, `renditions` (href, contentType, duration, width, height) and a first-class
  `restrictions` field; an unknown restriction is treated as restricted (`07_MULTIMEDIA…` §2).
- The **directory watcher** (ADR-010) ingests NewsML-G2 / ninjs sidecars and plain-text shotlists/scripts that arrive with
  footage. The footage file is recorded as a `media_asset` row (path, sha256, size, duration from the sidecar) and is
  **not** transcoded, copied, analysed or served by the MVP.
- Text that rides with video (shotlist, script, captions, transcripts) goes through the normal text pipeline.
- IPTC Media Topics (CC BY 4.0) may be used as the subject vocabulary later; not required for MVP.
- **Deferred:** licensed video ingest, MOS/BXF/MAM integration, scene detection, OCR, continuous ASR, video feed-health
  monitoring (black/freeze/silence/liveness), YouTube metadata.

## Consequences

- Deliverable 09 marks W3 (footage ingest/archive) and the video side of W4 (feed faults) OUT.
- A later video slice reuses items, dedup, events, queue and alerts; it adds a media worker (ffmpeg, cloud ASR) as a
  separate job type.
- The feed-fault detector design (tiers: no packets; black/silence; freeze while audio active) is kept for the video slice
  (`07_MULTIMEDIA…` §4).

## Evidence

[`technology/multimedia-and-broadcast-report.md`](../../technology/multimedia-and-broadcast-report.md) §1–§5 · [`technology/multimedia-standards-and-delivery.md`](../../technology/multimedia-standards-and-delivery.md) (F-H-08,
F-H-09, F-H-24, F-H-25) · [`experiments/multimedia/results.md`](../../experiments/multimedia/results.md) · [`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) DR-10.

## Reversal triggers

- A broadcaster pilot provides a legitimate feed or the AP Media Agent download directory with footage → first video slice:
  sidecar metadata normalisation (the KBS date-format problem, `01_INDUSTRY…` F-A-06), on-demand cloud ASR, thumbnails.
- A round-2 Korean ASR test (≈ $0.01) shows hosted ASR is accurate enough on Korean broadcast audio.
- The operator obtains a YouTube Data API key.
