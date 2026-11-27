# Roadmap

> **This is a list of possibilities, not a plan.** Nothing here has a date, an owner or a promise attached. Items may be
> reordered, changed or dropped, and most will never be built. The reasoning behind each lives in the
> [research library](../research/README.md).

## What exists today (v0.2.0)

- Collection of RSS/Atom feeds and of wire files placed in a watched folder (NewsML-G2, NITF, ninjs, plain text).
- Normalisation, exact and near-duplicate detection, wire versions, corrections and kills.
- Rule-based ranking from a desk profile, with the reasons shown, and search that works for Korean, Chinese and English.
- A local, loopback-only web queue. One process, one SQLite file, no account.
- Per-source licence flags that decide what is stored, displayed, sent to an AI model and published.
- Optional, off-by-default AI assessment of selected items ([`ai-enrichment.md`](ai-enrichment.md)).
- A static public export behind a deny-by-default redistribution permission ([`publication-policy.md`](publication-policy.md)),
  a synthetic and a live demonstration dashboard, and a Windows launcher.
- New in v0.2.0: editorial verdicts with notes and a shift report page; in-app alerts for priority items and
  failing feeds, with browser notifications while a tab is open; a technical check, classification and ingest tracking
  for wire video clips; search filters for band, time and footage, a failing-feed banner, and saved searches with
  alerts.

## What it does not do

- It lists items, not events. Related stories from different outlets are not grouped.
- It sends no e-mail and produces no scheduled digests; alerts and the shift report stay inside the app. It has no JSON
  API, authentication or backup.
- It does no speech-to-text, on-screen text or AI analysis of video. Wire clips are checked technically, but
  never filed into a newsroom or asset-management system.
- It has no connector for a news agency's own API. Licensed content arrives as files your agency software delivers.
- It has no social-media sources and no connection to newsroom, archive or asset-management systems.
- Ranking is keyword- and rule-based. It is transparent and misses meaning that keywords do not capture.

## Principles that bound every item below

- **Deterministic first.** Each capability must work without an AI model. AI stays optional, per source and per capability.
- **Licence flags decide.** Being able to collect, display or analyse an item never implies permission to republish it
  or to send it to a third party.
- **People decide.** Software ranks, drafts and flags. It does not send to outside parties or publish without approval.
- **Cloud services for model work.** Where a model is used (speech recognition, OCR, embeddings), it is a hosted service
  the operator configures, never a bundled model. Ordinary file and media handling stays local.
- **Loopback until authenticated.** Nothing listens beyond the local machine until there is authentication.
- **Measured, not assumed.** A capability counts when it passes a test with a known-answer and a no-answer control.

## Possible future capabilities, by area

### 1. Notifications

- Built (v0.2.0): in-page alerts with browser notifications for priority items and for feeds that keep failing,
  one alert per item.
- Still possible: e-mail and chat delivery, notices when a feed goes empty or silent, and suppression of repeats per
  story rather than per item (needs event grouping).
- Needs: an audit log, an outbox with approval rules, and recipient allow-lists. See
  [ADR-008](../research/architecture/adr/ADR-008-delivery-surface.md).

### 2. Reporting and editorial output

- Built (v0.2.0): per-item editorial verdicts with notes, and an on-demand shift report of the marked items.
- Scheduled and ad hoc briefings and shift handoff notes from deterministic templates, with citations to the items used.
- Reviewed, optionally AI-drafted text, labelled as such; a translation workflow for sources whose licence permits it.
- Curated collections, simple statistics, feed-health reports and document export.
- Needs: a notifier and outbox for e-mail; full-text storage only where a source allows it.

### 3. Audio and video

- Inspecting and converting media files; detecting black, frozen and silent stretches; speech-to-text; scene detection;
  on-screen text; subtitles; search over transcripts and metadata.
- Built (v0.2.0): technical inspection of wire clips with local ffmpeg, black and silence detection (frozen picture
  as a note), licence-gated thumbnails, classification by profile topics, ingest tracking and a CSV ingest sheet.
- Some of the rest has been tried outside the application on public-domain samples (one English clip, synthetic faults):
  see the [multimedia experiment](../research/experiments/multimedia/results.md) and
  [ADR-007](../research/architecture/adr/ADR-007-video-and-broadcast.md). Speech-to-text is not integrated. Korean speech recognition,
  noisy audio and live streams are untested.
- Needs: a separate media-processing job type, and media you are permitted to use.

### 4. Sources and connectors

- Connectors for news-agency APIs using the operator's own credentials; structured wire metadata; official public sources.
- Authorised social-media sources, only where a platform's terms and data-protection rules allow it.
- The software processes content the operator already licenses; the operator enters and attests each licence flag.
  See [ADR-010](../research/architecture/adr/ADR-010-source-connector-architecture.md).
- Needs: real sample deliveries to test against, and a decision on how time-limited restrictions such as embargoes are lifted.

### 5. Event-level intelligence

- Grouping items into events, matching stories across languages, tracking developments, counting independent sources,
  noting corroboration and conflict, and building timelines.
- Early measurements are in the [event-clustering experiment](../research/experiments/event-clustering/results.md) and
  [ADR-005](../research/architecture/adr/ADR-005-dedup-and-clustering.md). Deterministic grouping is conservative and misses many
  related stories. Linking a Korean story to its English source is weak with every method tried.
- Needs: a labelled test set from people who do this work, not only model-assisted labels.

### 6. Integration

- A read-only JSON API and read-only tools for an external AI assistant; export and import; a way to hand reviewed items to
  other systems (file or webhook).
- Newsroom, archive and asset-management integration is **not specified** and will not be until a real system, its interface
  document and sample data exist.
- Needs: authentication and roles before anything listens beyond the local machine.

## Two ways the project could grow

- **News intelligence:** text, alerts, reports, translation, events and coverage analysis, for any team that follows many
  sources.
- **Broadcast intelligence:** audio and video handling, speech recognition, classification, ingest, subtitles, fault
  detection and newsroom integration, for teams that receive footage.

Neither direction is chosen. They share the same collection, licence and ranking core.

## Where the detail is

- The full, unbuilt specification and task list: [`implementation-backlog.md`](../research/specification/implementation-backlog.md).
- What is built and why: [`decision-log.md`](../research/decision-log.md).
- How to give feedback: [`README.md`](../README.md#reporting-issues-and-contributing).
