# Changelog

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
