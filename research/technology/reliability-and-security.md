# Reliability and security review (Workstream J, S2, 2026-11-25)

> **Status: Design proposal (not built).** Reliability and security design. Only part of it is built.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Scope.** The MVP as specified in [`specification/mvp-specification.md`](../specification/mvp-specification.md) and [`architecture/recommended-architecture.md`](../architecture/recommended-architecture.md):
one Python process (FastAPI + APScheduler) over one SQLite file, public feeds plus a watched wire inbox, optional hosted
AI, a read-only MCP server. Video, browser automation and the deferred connectors are out of scope, except where an
excluded component could be switched on by mistake.

**How to read the tables.** Every risk has an ID (`J-Rnn` reliability, `J-Snn` security). Each row names the mitigation, the
backlog task that builds it ([`specification/implementation-backlog.md`](../specification/implementation-backlog.md)) and the test that proves it
([`specification/test-catalogue.csv`](../specification/test-catalogue.csv)). a private generator script fails if any J row cites no task or no test, or cites
one that does not exist.

**Evidence tags** follow [`evidence-conventions.md`](../evidence-conventions.md). TESTED rows cite phase-1 experiment files; nothing new was run for this
document. Library behaviour that was not checked in phase 1 is tagged INFERRED and is turned into a test instead of being
assumed. Date of every finding: 2026-11-25.

## 1. Reliability

### 1.1 Source availability

| ID | Failure mode | Evidence | Mitigation | Task | Test |
|---|---|---|---|---|---|
| J-R01 | A source times out, returns 5xx or 429, or DNS fails; the item stream stops | INFERRED; R6 saw NPR time out and UN News 403 ([`experiments/event-clustering/results.md`](../experiments/event-clustering/results.md)) | At most 3 attempts with backoff for timeout/5xx/429 only; every poll writes a `fetch_run` row; 3 consecutive failures open a `failing` incident and a `feed_incident` alert | T-14, T-35 | TS-FR03b, TS-FR04a |
| J-R02 | Silent null: HTTP 200 with 0 entries is read as "no news" | TESTED for RSSHub (returns 0 items on failure, [`experiments/repository-trials/rsshub.md`](../experiments/repository-trials/rsshub.md); [`technology/open-source-applications-evaluation.md`](open-source-applications-evaluation.md) F-C-02) | `empty` is a status, never a null; 200 + 0 entries against a non-zero 7-day median opens an `empty` incident | T-14, T-35 | TS-FR04b |
| J-R03 | A feed keeps answering 200 with stale items (publisher stopped updating it) | INFERRED | `silent` incident when no new item arrives for more than 6 × the median inter-arrival time (minimum 6 h) | T-35 | TS-REL-03 |
| J-R04 | A publisher changes robots.txt to disallow the feed; the system must stop, not bypass | INFERRED; DR-2 | RFC 9309 matcher re-checked daily; a disallow ends the poll with `error_class=robots`, counts toward a failing incident, and is never retried with another UA | T-12, T-35 | TS-FR02b, TS-REL-04 |
| J-R05 | Rate limits shared across one IP (GDELT allows one request per 5 s and the limit was effectively shared by parallel agents) | TESTED ([`experiments/event-clustering/results.md`](../experiments/event-clustering/results.md): 1 of 9 GDELT calls succeeded) | One serialised GDELT client; ≥ 5 s spacing; 429 backoff; per-feed interval floor of 300 s; one in-flight request per host | T-16, T-11, T-17 | TS-API-02, TS-FR02e, TS-SCH-01 |

### 1.2 Collection completeness

| ID | Failure mode | Evidence | Mitigation | Task | Test |
|---|---|---|---|---|---|
| J-R06 | Feed window overflow: a publisher posts more items between polls than the feed lists, so some are never seen | INFERRED (feeds carry a fixed window; R6 measured ~25 items per feed per day, so the risk grows on busy days) | Each poll records whether any entry overlaps the previous poll; overlap 0 logs a gap warning and appears in `/metrics` so the interval can be shortened (never below 300 s) | T-15, T-56 | TS-REL-06, TS-NFR12 |
| J-R07 | GDELT `lastupdate` files are skipped, or a timeline has missing days that read as zero | TESTED (`spike_detection/RESULTS.md`: 23 points for 30 days) | Track the 15-minute file sequence; a missing file is recorded as a gap; spike detection treats a missing bucket as missing, never zero | T-16, T-29 | TS-REL-07, TS-FR17c |
| J-R08 | Inbox files vanish before a scan (Media Agent can auto-delete), are read while still being written, or arrive with version gaps | DOCUMENTED (Media Agent auto-delete and `ItemID--Version--ContentID` layout, `02_COMMERCIAL…` §8.1) | 30 s scan; ingest only after size and mtime are stable; ledger marks `gone` without error; a version gap (v1 then v3) is logged | T-33 | TS-FR28c, TS-FR28f, TS-REL-08 |
| J-R09 | A server ignores conditional GET (CNA Taiwan does), so every poll re-downloads the feed | TESTED (`12_MVP…` §6 note; R5 probe) | Content-hash and natural-key dedup make a re-download harmless; bytes per run recorded | T-15, T-19 | TS-FR07b |
| J-R10 | Items without dates, or with unparseable dates, are dropped | TESTED (R6 dropped 50 undated rows from its corpus) | Keep the item with `published_utc=NULL`, the raw string and `first_seen_utc` | T-18 | TS-FR05a |

### 1.3 Latency

| ID | Failure mode | Evidence | Mitigation | Task | Test |
|---|---|---|---|---|---|
| J-R11 | New items reach the queue late: per-host serialisation, a growing write queue, or the queue waiting on AI | INFERRED; Haiku enrichment median 8.6 s per item ([`experiments/ai-processing/results.md`](../experiments/ai-processing/results.md)) | Enrichment runs after the item is visible (O1 view first, "AI 처리 대기" tag); write-queue depth in `/metrics`; latency measured against NFR-01 | T-17, T-56, T-62 | TS-NFR01a, TS-NFR12 |

### 1.4 Database integrity

| ID | Failure mode | Evidence | Mitigation | Task | Test |
|---|---|---|---|---|---|
| J-R12 | "database is locked" under concurrent writes from the pipeline and the web app | INFERRED from SQLite's single-writer model (ADR-004) | One writer thread fed by a queue; `busy_timeout`; web writes go through the same queue | T-07 | TS-DB-02 |
| J-R13 | A crash or power loss mid-transaction corrupts the file or leaves half-written units | INFERRED | WAL; one transaction per unit of work; `integrity_check` after every backup and at start-up; restore from the daily copy | T-07, T-54, T-62 | TS-NFR04, TS-NFR29a |
| J-R14 | The data directory sits on a network share, where WAL is unsupported | DOCUMENTED (sqlite.org/wal.html: WAL does not work over a network filesystem) | `doctor` refuses a UNC or network path for the data dir | T-58 | TS-REL-14 |
| J-R15 | Disk fills (backups, logs, bodies) and writes fail | INFERRED | Free space in `/healthz`; backup skipped with an ops alert when space is short; DB size in `/metrics` | T-54, T-56 | TS-REL-15, TS-NFR12 |

### 1.5 Recovery after interruption

| ID | Failure mode | Evidence | Mitigation | Task | Test |
|---|---|---|---|---|---|
| J-R16 | The process dies mid-ingest or mid-send: items duplicated, emails lost or sent twice | INFERRED | Natural keys make re-ingest idempotent; the inbox ledger makes directory ingest restart-safe; the outbox is a state machine with a Message-ID idempotency key, so a resend after a crash is at-least-once and identifiable | T-17, T-19, T-36, T-62 | TS-NFR04, TS-NFR04a, TS-REL-16 |
| J-R17 | A migration fails half way and leaves an unusable schema | INFERRED | Automatic pre-migration backup that passes `integrity_check`; migrations run in a transaction; rollback is `newsmon restore` | T-54, T-07 | TS-NFR28b |
| J-R18 | The AI provider is down or refuses; items disappear from the desk view | INFERRED (R7 saw 0 refusals in 142 calls, [`technology/ai-threat-model.md`](ai-threat-model.md) T8) | Items stay visible as O1 rows marked `pending`; a worker drains them with backoff on recovery; header shows "AI: 중단" | T-47, T-52, T-60 | TS-FR15b, TS-AIS-02 |
| J-R19 | A retry storm or misrouting runs up AI spend | INFERRED; Sonnet ≈ 21× Haiku per item (TESTED cost ratio, [`experiments/ai-processing/results.md`](../experiments/ai-processing/results.md)) | Daily USD cap with degradation to O1 until midnight KST; one retry per item, never a bulk retry; alarm at 2× expected spend | T-47, T-49 | TS-FR15c, TS-FR13b, TS-NFR09 |
| J-R20 | The scheduler thread dies while the web app stays up, so nothing is collected but the UI looks healthy | INFERRED | Heartbeat row per tick; `/healthz` turns unhealthy when the tick is older than 2 cycles | T-17, T-56 | TS-REL-24 |

### 1.6 Reproducibility

| ID | Failure mode | Evidence | Mitigation | Task | Test |
|---|---|---|---|---|---|
| J-R21 | The same inputs give different groupings, bands or summaries on re-run, so results cannot be traced | INFERRED | Algorithm id on every membership row; fixed MinHash seed; deterministic TF-IDF; model id stored with every vector; model, prompt version and schema version on every AI row; pinned lock file | T-27, T-20, T-50, T-47, T-57 | TS-NFR16, TS-O3-02, TS-FR11c, TS-NFR18 |
| J-R22 | Time zone or clock errors: KST shown as UTC, DST assumptions, skew breaking the silent-feed rule | INFERRED | UTC storage, KST display only (no DST in KST); a `Clock` port so tests control time; intervals measured on the monotonic clock | T-02, T-42 | TS-NFR14 |
| J-R23 | Backups keep content past `retention_days`, so a purge receipt is false (DR-21) | INFERRED: default 14 dailies vs `mock_wire_gated` `retention_days=7` | Backup rotation capped at the shortest retention of any active full-storage source; the purge receipt lists deleted backups | T-54, T-25 | TS-REL-22, TS-FR06e |

### 1.7 Observability and instrument nulls

| ID | Failure mode | Evidence | Mitigation | Task | Test |
|---|---|---|---|---|---|
| J-R24 | Failures are invisible: no structured record of fetches, AI calls, alerts, sends and errors | INFERRED | JSON-lines logs with correlation ids (§1.8); `/metrics` values checked against the fixture run's tables by a second computation | T-09, T-56 | TS-NFR13, TS-NFR12 |
| J-R25 | An empty search result during a feed incident is read as "no news" | TESTED analogue: `trigram MATCH` returned nothing for 2-character queries (`korean_fts/RESULTS.md`) | Bigram index with known-answer and nonsense controls in CI; the search page shows a banner for failing feeds inside the filter and never says "no news" | T-32, T-43 | TS-FR20a, TS-FR20b, TS-FR20-banner |

### 1.8 What to log and which health metrics to expose

**Logs** (JSON lines to stdout, one record per event, each with `ts`, `level`, `event`, `correlation_id`, `workspace_id`;
T-09). Content policy: ids, hashes, counts and flags only. **Never** source text, AI output text, secrets or recipient
message bodies (J-S18).

| Event | Fields |
|---|---|
| `fetch_run` | feed_id, source key, attempt, status, http_status, error_class, bytes, entries, new_articles, overlap_with_previous, duration_ms, licence flag snapshot id |
| `inbox_scan` | feed_id, files_seen, ingested, quarantined, gone, version_gaps |
| `quarantine` | raw_ref, reason |
| `ai_call` | task, provider, endpoint_kind, region, model, prompt_version, fields_sent, input_sha256, tokens in/out, cost_usd, latency_ms, validation_status, injection flags, cache_hit |
| `ai_skip` | article uid, reason (`not_allowed`, `capped`, `capability_off`, `no_key`) |
| `alert` | kind, event uid, band, rule ids, auto_send or awaiting_approval |
| `send` | msg_id, channel, recipient domain (not the full address), result, attempt |
| `incident` | feed_id, kind, opened/closed |
| `purge` / `takedown` / `export` / `backup` | counts, receipt id, file paths inside the data dir |
| `error` | component, exception class, redacted message |

**Health metrics** (`/healthz` and `/metrics`, T-56; NFR-12):

| Metric | Why |
|---|---|
| Process up, DB writable, scheduler heartbeat age, last pipeline tick | Detect J-R20 |
| Fetch success rate per feed and overall (24 h); open incidents by kind | Source availability (J-R01…J-R04) |
| Items per hour per feed vs 7-day median; overlap-0 count; GDELT gaps; inbox `gone` before ingest | Completeness (J-R06…J-R08) |
| Write-queue depth; p95 first-seen-to-visible latency (computed from rows) | Latency (J-R11) |
| Enrichment backlog (`pending`), review-queue size, validation failure rate, injection flag rate | AI health |
| AI spend today vs cap, `capped` flag, 2× alarm state | Spend (J-R19) |
| Alerts sent / awaiting approval / dismissed (24 h) | Alert load |
| DB size, free disk, last good backup age | Integrity (J-R13, J-R15) |

## 2. Security

Trust boundary (from [`technology/ai-threat-model.md`](ai-threat-model.md) §1): everything fetched from feeds, pages and wire files is **untrusted data**.
Only operator-written prompts, profiles, configuration and the metadata the collector itself parsed are trusted.

### 2.1 Prompt injection (R7 threat model and experiment)

R7 TESTED, on 11 articles with obvious English payloads: 0/24 hijacks in tool-less schema-constrained calls; 48/48 attacked
calls flagged `injection_suspected`; 0 false positives on 44 clean hardened calls; **a subtle score attack still moved Haiku
by +22.6 points and Sonnet by +8 while the flag was set** ([`experiments/ai-processing/results.md`](../experiments/ai-processing/results.md), [`technology/ai-threat-model.md`](ai-threat-model.md) T2).

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S01 | Instruction hijack of an enrichment or triage call (T1) | No `tools` on any content call (static and runtime checks); schema-constrained output; article delimited and declared untrusted; three validation layers | T-03, T-46, T-49 | TS-ARCH-04, TS-NFR08, TS-FR14a |
| J-S02 | Score or priority manipulation (T2, partly succeeded in R7) | Bands, not scores; the LLM band is capped at `report` and only rules can set `flash`; a flagged item has its LLM band discarded and goes to review with ⚠; the regex pre-filter is OR-ed with the model flag | T-45, T-48, T-49 | TS-FR11a, TS-SEC-02, TS-FR14a |
| J-S03 | Payload echo into reader-facing fields (T3: 2/6 Sonnet naive, 0/12 hardened) | Hardened prompt; AI text always labelled "AI 생성" with model; source text kept separate and immutable | T-49, T-42 | TS-FR19b, TS-FR12a-stub |
| J-S04 | Exfiltration by rendering (T5: an exfil URL did appear in model output) | Model output rendered as plain text, links, images and URLs removed; Content-Security-Policy blocks remote images and inline script | T-22, T-42 | TS-FR25a, TS-SEC-04 |
| J-S05 | Injections the model does not flag: Korean and Chinese payloads, injections inside quotations, attribution laundering (residual risk, untested in R7) | KO/ZH regex patterns and hidden-text checks; flagged or not, nothing an LLM says can trigger an external send or a flash; round-2 attack set (deliverable 14 E7) | T-45, T-63 | TS-FR14b, TS-EVAL-02 |

### 2.2 Malicious pages, feeds and wire files

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S06 | Script or markup in feed titles and summaries (stored XSS in the queue); oversized or slow responses | HTML stripped at normalisation; Jinja2 autoescape; CSP; 10 MB cap and 30 s timeout | T-18, T-42, T-11 | TS-SEC-06, TS-SEC-04, TS-NFR06 |
| J-S07 | XML attacks in RSS or wire files: external entities (XXE), entity expansion (billion laughs) | Wire XML parsed with defusedxml (pin at build); feedparser only parses bytes the fetcher already downloaded, and an external-entity RSS fixture must cause no file read or request (feedparser's behaviour is INFERRED, so it is tested) | T-34, T-15 | TS-FR29d, TS-SEC-07, TS-SEC-06x |
| J-S08 | Malformed or hostile wire files crash the parser | Content detection; quarantine with reason; connector never raises | T-34, T-14 | TS-FR29c, TS-FR27c |

### 2.3 Untrusted media files

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S09 | A media file exploits a decoder, or a file disguised by extension is parsed as something else | Media are recorded only (path, sha256, size from the sidecar); never decoded, transcoded, thumbnailed or served; type by magic bytes; per-file size cap | T-34, T-33 | TS-FR29e, TS-SEC-08 |
| J-S10 | Path escape from the inbox: symlinks, `../` in rendition hrefs, writes into the customer's folder | Real-path confinement; symlink escape refused; hrefs stored as text, never followed; watcher never writes, moves or deletes | T-33, T-34 | TS-FR28d, TS-FR28e, TS-SEC-08 |

### 2.4 SSRF in the fetcher

Phase-1 evidence: changedetection.io's API accepted watches on `http://127.0.0.1:5099/` and
`http://169.254.169.254/latest/meta-data/` (TESTED, private experiment data (not published)).
The guard therefore has to live in newsmon's own client and cannot be delegated to a sidecar.

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S11 | Feed URLs, redirects or DNS answers that point at loopback, private, link-local or cloud-metadata addresses | Resolve once and connect to the vetted IP (no re-resolution, so DNS rebinding fails); refuse loopback, RFC 1918, CGNAT, link-local, multicast, 0.0.0.0, IPv6 ULA and link-local, IPv4-mapped IPv6 and metadata addresses; re-check every redirect hop; `http`/`https` only; alternative IP spellings normalised before the check | T-11 | TS-FR02d, TS-SEC-09 |
| J-S12 | Article links inside a feed are attacker-controlled; the body fetch follows them | Body fetch uses the same guarded client and robots check; only for sources with `storage ≥ transient` | T-23 | TS-SEC-09b, TS-FR06a |
| J-S13 | The test-only allowance for the loopback fixture server leaks into production | The allowance is an injected policy object; the settings schema has no key for it; an architecture test fails if code outside `tests/` builds one | T-11, T-03 | TS-SEC-10 |

**Allow-list stance.** The fetcher is a deny-list on address class plus an allow-list on scheme. Feed URLs themselves come
only from `sources.yaml` or the admin UI (admin role), so the source registry is the effective allow-list of hosts; no API,
MCP tool or AI output can add a URL to fetch (J-S20).

### 2.5 Browser automation and optional sidecars

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S14 | Browser automation (Playwright, stealth fetching) creeps into the core, breaking DR-2 and adding a large attack surface | Excluded from the MVP (ADR-001, DR-2); an architecture test fails on any browser-automation or local-model import in `src/` | T-03 | TS-ARCH-07 |
| J-S15 | A `changedetection` or `rsshub` source is activated before its adapter and isolation exist (the sidecar itself accepts internal URLs, J-S11 evidence) | Registry refuses to activate those access methods in the MVP ("adapter not implemented"); when built later they run as separate services with their own egress rules | T-13 | TS-SEC-12 |

### 2.6 Credential exposure

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S16 | API keys or SMTP or wire credentials leak through logs, exceptions, the DB, API, MCP, emails, exports or config export | All secrets through `SecretStore` (env/.env); redaction filter seeded with the secret values; secrets never stored in the DB or config; export carries secret names only; canary greps over every output of the e2e run | T-09, T-55, T-59 | TS-NFR07a, TS-NFR07, TS-NFR26, TS-FR26c |
| J-S17 | Secrets read ad hoc from the environment in random modules, bypassing the store and its owner tag | Architecture test: no secret reads outside `adapters/secrets`; each credential tagged with its owner, customer or provider (DR-15, DR-22) | T-03, T-09 | TS-ARCH-03, TS-NFR27b |

### 2.7 Dependency vulnerabilities and supply chain

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S18 | A known-vulnerable dependency ships | `uv.lock` with hashes; `pip-audit --strict` in CI on Windows and Ubuntu, release blocked on high/critical (NFR-18); SBOM per build; vendored htmx checked against a recorded hash | T-57 | TS-NFR18 |
| J-S19 | A forbidden licence (AGPL, SSPL, GPL, Sustainable Use) or an unvetted operator tool (datasette, datasette-mcp) enters the core set | Licence gate with a positive control; excluded-package test | T-57 | TS-NFR31, TS-SEC-25 |

### 2.8 Unauthorised external actions

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S20 | The system emails outsiders, or notifies a wire agency, without a person deciding | Outbox rule: automatic sending only to allow-listed internal recipients and only for unflagged items; everything else `awaiting_approval`; outside notices about feed incidents are always drafts; no API, MCP tool or AI output can create a send or a fetch | T-36, T-37, T-35, T-53 | TS-FR21d, TS-FR21c, TS-FR04d, TS-FR24a |
| J-S21 | Web-surface abuse: unauthenticated API reads, CSRF on verdicts and approvals, brute-force logins, a server exposed beyond localhost | `AuthProvider` with roles; hashed tokens with scopes; CSRF token on every write; login throttle; default bind 127.0.0.1; TLS by a reverse proxy on the VPS | T-39 | TS-NFR25, TS-FR23a, TS-SEC-21 |
| J-S22 | SQL injection through search terms, filters or profile values | Parameterised queries only, enforced by an AST test; all SQL in `repo/` | T-03, T-07 | TS-ARCH-06, TS-ARCH-02 |
| J-S23 | Regular-expression denial of service from admin-entered boilerplate patterns or keywords | Profile keywords are literals (escaped); boilerplate regexes validated at load with a length cap and a time-boxed trial | T-18, T-30 | TS-SEC-23 |

### 2.9 Data leakage

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S24 | Licensed text reaches a hosted model against the customer's flags (`external_ai_allowed=false`, `ai_processing=no`, op not in `permitted_ops`) | One router decides per item and capability; `fields_sent` logged per call; stub call-log assertions on the gated mock wire | T-47, T-22 | TS-FR15d, TS-FR10d, TS-FR12b, TS-GATE-01 |
| J-S25 | Text shown, exported or emailed beyond `display`, `redistribution` or `authorised_users` | `DisplayPolicy` is the only renderer for UI, API, MCP, digest and export; tests check every surface for a canary summary string | T-22, T-40, T-53, T-55, T-38 | TS-FR06c, TS-FR06d, TS-NFR29c, TS-FR24b |
| J-S26 | Licensed text in logs (logs are often shipped to third-party tools) | Logging policy: ids and hashes only; a canary sentence from the gated wire fixture must not appear in any log line | T-09, T-59 | TS-SEC-18 |
| J-S27 | Cross-instance leakage through shared caches (DR-19), for example library caches under the user's home | All caches inside `NEWSMON_DATA_DIR`; tldextract offline with its bundled list; two-instance test diffs the files each instance touches | T-21, T-61 | TS-TLD-01, TS-NFR24 |
| J-S28 | Personal data in news text sent to a US-hosted LLM without a legal route (PIPA §28-8, OQ-5) | Provider and region from config; `fields_sent` logged; entity-masking switch for PERSON gazetteer entries; no person-profile pages | T-47, T-42 | TS-NFR15a, TS-NFR15b |
| J-S29 | Content kept after the licence ends, or a takedown leaves copies in the search index | `valid_until` kill switch; retention purge and takedown also delete FTS rows and AI outputs, with receipts | T-24, T-25 | TS-FR30b, TS-FR26b, TS-SEC-27 |
| J-S30 | Third-party text used for training | `training` fixed to `no` by a CHECK; no training or fine-tuning call path | T-07, T-03, T-46 | TS-FR01d, TS-ARCH-05, TS-NFR19 |

### 2.10 AI tool access

| ID | Threat | Mitigation | Task | Test |
|---|---|---|---|---|
| J-S31 | Tools attached to a content-processing call turn an injection into an action (T4) | `tools` absent from every content call, checked statically and on captured requests | T-03, T-46 | TS-ARCH-04, TS-NFR08 |
| J-S32 | An external agent over MCP writes data, runs SQL, fetches URLs, or chains returned article text into actions (T6) | Exactly 8 read tools; DB opened read-only; source text under `untrusted_source_text` with `content_trust`; gated items return metadata and headline only; limit 50; every call audited. The client agent itself stays outside the system's control (residual) | T-53 | TS-FR24a, TS-FR24c, TS-FR24d, TS-FR06c-mcp |
| J-S33 | An AI provider adapter connects to an unexpected host, or AI is silently on when the operator thinks it is off | AI hosts from config only; O1 default with every capability false; header shows the real state; the O1 acceptance run asserts 0 connections to any AI host | T-02, T-52, T-59 | TS-U-settings, TS-ACO1-03, TS-ACO1-01 |

## 3. Residual risks (accepted for the MVP, stated)

- **Unflagged subtle injection** (J-S05): reduced to "a person sees it at review band", not eliminated.
- **The MCP client agent** (J-S32) can still act on returned text in the user's own environment.
- **Real customer wire output is untested**: parsers are proven on synthetic fixtures only (ADR-010).
- **Linux install and symlink refusal** are verified only in the Ubuntu CI job; the Dockerfile is untested (no Docker,
  P-004).
- **At-least-once email** after a crash mid-send (J-R16): a duplicate flash email is possible and identifiable by
  Message-ID; a lost one is not accepted.
- **Feed window overflow** (J-R06) is detected, not prevented: items that scroll out of a feed between polls are gone.
