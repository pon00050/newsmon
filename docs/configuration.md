# Configuration and operation

Newsmon reads a configuration folder and writes a data folder. Both come from the environment
(`NEWSMON_CONFIG_DIR`, `NEWSMON_DATA_DIR`) or from `--config` / `--data`. The Windows launcher and `newsmon-desktop` use
`%LOCALAPPDATA%\Newsmon\config` and `...\data` and copy `config.example/` there on first start.

## Pipeline

```
sources.yaml ─┬─ RSS/Atom feeds ── HttpFetcher (UA, robots.txt, SSRF guard, 10 MB / 30 s caps, one request per host)
              └─ inbox directory ─ watcher (read-only, stable-file check, ledger) ─ NewsML-G2 / NITF / ninjs / plain text
   → normalise (canonical URL, clean text, language, UTC time, content hash; bad records → quarantine)
   → licence gate (storage flags decide what is kept) → SQLite (WAL)
   → dedup (GUID / URL / content hash, MinHash near-dups, revisions, wire versions and kills)
   → rules (profile keywords, watch entities, source weights, wire urgency, recency → band + explanation)
   → search index (FTS5 with CJK bigrams) → web queue / search / item detail / source status (DisplayPolicy on every page)
```

## Configuration files
Start from `config.example/`:

- `settings.yaml`: `use_context` (private | internal), fetch User-Agent, inbox scan interval, UI port. All
  `ai.capabilities` are false (O1, deterministic).
- `sources.yaml`: one row per source with its licence flags (`storage`, `display`, `allowed_contexts`, …). Defaults for
  missing flags are the safe choice (metadata only, headline only). A `directory` source's `path` is relative to the
  config directory. Customer sources (`licence_owner: tenant`) stay inactive until attested with `retention_days`.
- `profiles/*.yaml`: what to watch and how to rank (topics with KO/EN/ZH keywords, watch entities, source weights and
  mutes, excluded keywords, priority rules, score thresholds). Edits take effect at the next collection, no restart.
  The first profile by key ranks the queue.
- `gazetteer.yaml`: watch entities with KO/EN/ZH aliases (used for ranking and search alias expansion).
- Secrets never go in these files (the loader refuses them); put them in the environment or `<config>/.env`.

## Commands

| Command | What it does |
|---|---|
| `newsmon init` | create or upgrade the database, load sources and profiles, report what was loaded |
| `newsmon collect` | one collection cycle over every source that is due (`--force` ignores intervals, `--source KEY` limits it) |
| `newsmon collect --loop` | keep collecting; each feed at its own interval (≥ 300 s), the inbox every `inbox.scan_seconds` |
| `newsmon serve` | local web UI on http://127.0.0.1:8765/ (loopback only); the "지금 수집" button runs a cycle; `--auto-collect` also collects in the background |
| `newsmon status` | sources, last fetch result, consecutive failures, counts, rejected profiles |
| `newsmon search "<query>"` | the same search as the web page (KO/EN/ZH; gazetteer aliases expanded) |
| `newsmon rerank` | reload profiles and re-rank stored articles |
| `newsmon enrich` | run optional AI enrichment now (A.1; `--uid` for chosen articles, `--limit N`, `--stale` to reassess items assessed under an earlier profile, model or prompt) |

Prefix with `uv run` when the venv is not activated. One process and one SQLite file is the whole runtime.

### Diagnosing a failure

Every collection attempt is a `fetch_run` row and every rejected record a `quarantine` row whose reason starts with the
stage (`collect:`, `parse:`, `normalise:`, `persist:`). `newsmon status` and the 소스 상태 page show both per source.
Logs are JSON lines on stderr with `source`, `stage`, `error_class` and a per-cycle `correlation_id`; source text is
never logged and secret values are redacted. One failing source never stops the others.

Stages and where they live: collect `connectors/feed.py`, `connectors/directory.py`, `fetcher/`; parse
`connectors/feed.py`, `connectors/wire.py`; normalise `pipeline/normalise.py`; permission `licence/policy.py`;
persistence and dedup `repo/articles.py`, `pipeline/dedup.py`; ranking `rules/`; search `pipeline/tokenize.py`,
`repo/articles.py`; presentation `web/`.

## Known limits

- No event grouping: the queue lists items (duplicates collapsed onto the earliest copy), not events. FR-09's
  independent-source count is therefore per duplicate group, not per event.
- AI (A.1) is optional and licence-gated; with it off there are no Korean summaries or translations of foreign text.
- No alerts, email, digests, JSON API, MCP, authentication, backup/restore or data export beyond `export-public` (see `docs/ROADMAP.md`).
- `http_api` sources (Federal Register, GDELT) load inactive: the HTTP API connector is not built yet.
- Symlink-escape refusal is implemented but cannot be exercised on this Windows machine without developer mode.
- AI assessments reflect the profile as it was when the item was assessed. They are counted as stale on the AI page
  after a profile edit and refreshed only on request (`newsmon enrich --stale`), never automatically.
- A restriction on a wire item caps its display at the headline and keeps it from AI processing, and it stays for the
  life of the item: an embargo that has since passed, or a `withheld` item later re-issued as usable, is not released
  automatically. The text of `usageterms`, rights notices and editor's notes is not interpreted.
- Ranking is recomputed for every stored article on each cycle because scores age with time (about 0.6 s per 1,000
  articles measured on this machine). This is the first thing to change if the database grows by orders of magnitude.
- `newsmon status` and `newsmon search` open the database the same way `collect` does, so they also apply migrations
  and reload sources and profiles; they are not read-only.
- Licence flags are snapshotted per article at ingest: changing a source's flags affects articles collected afterwards.
