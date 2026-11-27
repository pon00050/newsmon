# Changelog

## Unreleased

- **Editorial verdicts.** Each queue row and item page can be marked 보고 (report to desk), 확인 (needs verification) or
  무시 (ignore), with an optional note; `r` / `v` / `x` on the queue act on the selected row. Verdicts are append-only
  and the newest one per item is current. The name recorded is `desk_editor` in `settings.yaml` (there is no login).
- **Shift report** (`/shift-report`, 교대 보고). Items marked 보고 or 확인 in the last N hours, flagged when an item was
  withdrawn or revised after the verdict. It carries headline, source, link, times, ranking reasons and the note only,
  never a summary, body or AI text. Printable and downloadable as one HTML file.
- **In-app alerts.** After each collection: `flash` items, optionally `report`-band items (profile `alerts: report:`),
  and feeds whose last 3 polls failed (and their recovery). A 🔔 badge on every page, an alerts page with acknowledge
  and dismiss, and browser notifications while a tab is open. One alert per item; duplicates and injection-flagged
  items raise none; no e-mail yet.
- The database enforces one alert per item and kind, and one open incident per feed (migration 0003). An `alerts:`
  entry set to `false`, or listing channels without `inapp`, is off.
- Fix: the source-status page counted each retry as a separate failure, so one failed poll showed as 3.
- Fix: a test hard-coded 2026-11-27 as "tomorrow" and failed from that date.

## 0.1.0 — 2026-11-25

First public release.

- Collection of RSS/Atom feeds and a watched folder of wire files (NewsML-G2, NITF, ninjs, plain text), with
  robots.txt, polite intervals, SSRF protection and size/time limits.
- Normalisation, exact and near-duplicate detection, wire versions, corrections and kills.
- Profile-based ranking with explanations; KO/EN/ZH keyword topics, watch entities, source weights.
- Korean/Chinese-aware full-text search (FTS5 with CJK bigrams).
- Local web queue, search, item detail and source health (loopback only).
- Per-source licence flags controlling storage, display and AI use; restrictions, embargoes and withdrawals enforced.
- Optional, licence-gated AI assessment (off by default, daily cost cap).
- New in the public release: `newsmon export-public` with a separate, deny-by-default public-redistribution gate;
  `newsmon-desktop` and the double-click `Start-Newsmon.cmd` launcher for Windows; the project website with
  synthetic and live dashboards and the research library; CI on Linux and Windows.

Known limitations: no event grouping, alerts, digests, API, authentication, backup or video processing. See
`docs/ROADMAP.md`.
