# 10 · Build vs. reuse matrix (S1, 2026-11-25)

> **Status: Design proposal (not built).** Deliverable 10. This document describes the FULL MVP. Most of it is not built: Release A + A.1 implements only a subset (collection of authorised feeds and wire files, normalisation, deduplication, rule ranking, search, a local queue, and optional AI assessment). See the [decision log](../decision-log.md) for what is built.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Classes:**

| Class | Meaning |
|---|---|
| **Adopt** | Use the package as is, as a dependency |
| **Extend** | Use it and add our own code on top or plug-ins |
| **Integrate** | Run a separate application and talk to it over an API |
| **Implement** | Write it ourselves (we may copy algorithm ideas from permissively licensed references) |
| **Defer** | Not in the MVP |

**Sources:** licences come from [`technology/components-registry.csv`](../technology/components-registry.csv) and
[`sources-and-licensing/oss-licenses.csv`](../sources-and-licensing/oss-licenses.csv), verified 2026-11-25. Evidence paths point to phase-1 files.
**Tags:** T = TESTED here · V = VERIFIED · D = DOCUMENTED · I = INFERRED.

| # | Component | Class | Package / repo | Licence | Evidence | Note |
|---|---|---|---|---|---|---|
| 1 | Feed parsing | **Adopt** | feedparser 6.0.14 | BSD-2 | T `component_smoke/results.json`, `supplement_results.json` (conditional GET) | Stateless; we keep ETag and Last-Modified in `feed` |
| 2 | HTTP client with UA, conditional GET, per-host lock, SSRF refusal at connect time | **Extend** | httpx 0.28.1 + own transport hook | BSD-3 | T smoke; SSRF pattern V from miniflux and changedetection ([`technology/open-source-applications-evaluation.md`](../technology/open-source-applications-evaluation.md) security notes) | httpx's last release was 2024-12, but the repo is active (F-C-07 flags) |
| 3 | robots.txt matcher | **Implement** | Own RFC 9309 matcher (do not use `urllib.robotparser`) | — | T [`sources-and-licensing/acquisition-methods.md`](../sources-and-licensing/acquisition-methods.md) §3 (robotparser `?` bug found by control) | Port R5's matcher from [`experiments/source-collection/probe_sources.py`](../experiments/source-collection/probe_sources.py) |
| 4 | Feed ingest state (reader) | **Defer / Reject** | lemon24/reader 3.27 | BSD-3 | T works; rejected for schema and UA reasons (ADR-001) | — |
| 5 | Article body extraction (only where `storage` ≥ transient) | **Adopt** | trafilatura 2.4.0 + per-source Korean boilerplate regex | Apache-2.0 | T [`technology/open-source-components-evaluation.md`](../technology/open-source-components-evaluation.md) F-C-03 | Not called for metadata-only sources |
| 6 | Date / JSON-LD cross-check | **Defer** | htmldate 1.11.0, extruct 0.18.0 | Apache-2.0 / BSD-3 | T F-C-03 | Only needed once bodies are fetched at scale |
| 7 | URL canonicalisation | **Extend** | courlan 1.5.0 + fragment strip | Apache-2.0 | T F-C-04; R6 dedup | — |
| 8 | Registrable domain (eTLD+1) | **Adopt** | tldextract 5.4.0, using its bundled suffix list | BSD-3 | I: installed in the smoke env; R6 used a heuristic (`syndication_breakdown.py`) | Verify offline mode at build |
| 9 | Content hash, normalisation, language by script ratio | **Implement** | stdlib (`hashlib`, `unicodedata`) | — | T R6 pipeline | py3langid 0.4.0 is a fallback for "other" scripts only (Defer) |
| 10 | Near-dup detection | **Adopt** | datasketch 2.0.0 MinHash-LSH | MIT | T [`experiments/deduplication/results.md`](../experiments/deduplication/results.md) | 128 perms, char 4-grams |
| 11 | Revision / live-blog / story_key rules | **Implement** | own, configured per source | — | T failure cases in [`experiments/deduplication/results.md`](../experiments/deduplication/results.md) | — |
| 12 | Event clustering (incremental) | **Implement** | own (numpy 2.5.5) | BSD-3 | T [`experiments/event-clustering/results.md`](../experiments/event-clustering/results.md), `cluster_experiment.py` | Port R6's algorithm |
| 13 | TF-IDF fallback clustering | **Adopt** | scikit-learn 1.9.1 | BSD-3 | T same | — |
| 14 | Embeddings | **Integrate** (cloud API) | OpenAI `text-embedding-3-small` | provider terms | T same ($0.002 for 826 items) | Behind `AIProvider.embed` |
| 15 | LLM triage and enrichment | **Integrate** (cloud API) + **Implement** prompts and validators | anthropic 2.14.0, pydantic 2.14.4 | MIT / MIT | T [`experiments/ai-processing/results.md`](../experiments/ai-processing/results.md) | Port R7's v2 schema and the hardened system prompt (private experiment data (not published)) |
| 16 | AI provider router, cache, spend cap, injection regex | **Implement** | own | — | T guard pattern in `run_experiments.py`; M4/M5 design in [`technology/ai-threat-model.md`](../technology/ai-threat-model.md) | — |
| 17 | Customer-hosted AI endpoint adapter (customer's own cloud region or hardware) | **Defer** (designed) | OpenAI- or Anthropic-compatible HTTP | — | I ADR-006, ADR-010 | Nothing runs locally |
| 18 | Spike detection | **Implement** | own rolling z-score | — | T `spike_detection/RESULTS.md` | — |
| 19 | Storage | **Adopt** | SQLite 3.50.4 (stdlib `sqlite3`), WAL | public domain | T F-C-06 | — |
| 20 | Search index (CJK bigram pre-tokenisation over FTS5) | **Implement** on **Adopt**ed FTS5 | own tokeniser function | — | T `korean_fts/RESULTS.md` (method D) | Regression suite from `fts_experiment.py` |
| 21 | Vector index | **Defer** | sqlite-vec 0.1.9 | MIT/Apache-2.0 | T loadable (F-C-06) | Until archive-wide semantic search is needed |
| 22 | Korean morphology | **Defer** (pending project-owner decision) | kiwipiepy 0.25.1 | Apache-2.0 | T runs; flagged for no-local-inference policy (F-C-05) | Not required: bigram reaches recall 1.00 |
| 23 | Repository layer and migrations | **Implement** | own (plain SQL files plus a version table) | — | I ADR-004, ADR-009 | No ORM is needed; it could be added later |
| 24 | Scheduler | **Adopt** | APScheduler 3.11.3 (in process) | MIT | T F-C-07 | — |
| 24b | YAML configuration parsing (`config/*.yaml`) | **Adopt** | PyYAML (pin at build; use `safe_load` only) | MIT | I (added after review; S2 gap 3) | Omitted from the first version of this matrix |
| 25 | Web app and JSON API | **Adopt** FastAPI 0.165.0 + uvicorn 0.54.0 + Jinja2 3.1.6; **Implement** pages | | MIT / BSD-3 / BSD-3 | D for FastAPI (registry metadata); T for uvicorn and Jinja2 being importable (smoke env) | — |
| 26 | UI interactivity | **Adopt** | htmx 4.0.2 (vendored static file) | 0BSD | D registry metadata | Server-rendered; no SPA build chain |
| 27 | Editorial queue, event detail, digest editor, profile editor | **Implement** | own | — | I [`specification/interface-spec.md`](../specification/interface-spec.md) | Patterns from AISURFER Brief (draft → review) and Horizon/feeds.fun (profiles, rules over tags) |
| 28 | Rules engine (profiles → bands) | **Implement** | own | — | I; references Huginn Trigger, feeds.fun, AIHOT tiers (MIT/BSD, [`technology/open-source-applications-evaluation.md`](../technology/open-source-applications-evaluation.md)) | Copy ideas, not code from no-licence repos |
| 29 | Email delivery | **Adopt** | stdlib `smtplib` | PSF | I | — |
| 30 | Other notification channels | **Defer** | apprise 2.3.0 | BSD-2 | T parse-only (F-C-07) | Messenger evidence: UNVERIFIED-absent |
| 31 | MCP server (read-only, stdio) | **Extend** | official Python MCP SDK (FastMCP), version pinned at build | MIT (verify) | D [`technology/mcp-tool-design.md`](../technology/mcp-tool-design.md) §1 | Tools wrap the service layer |
| 32 | Generic SQLite MCP | **Reject** for the product | datasette-mcp | Apache-2.0 | V metadata ([`technology/mcp-servers-evaluation.md`](../technology/mcp-servers-evaluation.md)) | Bypasses `DisplayPolicy` (ADR-008); operator debugging only |
| 33 | Datasette (operator view) | **Defer** (optional tool) | datasette 0.65.6 | Apache-2.0 | T serving SQLite (F-C-06) | Run on a read-only copy only |
| 34 | Connector contract and `feed` / `http_api` connectors | **Implement** | own | — | I ADR-010 | — |
| 35 | Directory watcher (inbox) | **Implement** | own (polling, stdlib `os.scandir`) | — | I ADR-010 | No `watchdog` dependency is needed |
| 36 | NewsML-G2 (XML/JSON) / NITF / ninjs / plain-text wire parsers (AP Media Agent formats VERIFIED, `02_COMMERCIAL…` §8.1) | **Implement** | own + defusedxml (pin at build, not evaluated) | PSF (verify) | V field sets (`07_MULTIMEDIA…` §2); Superdesk parsers V as a reference (AGPL: read, do not copy) | Synthetic fixtures |
| 37 | AP Media API / Reuters Connect connectors | **Defer** (designed) | own, referencing Superdesk `ap_media.py` | AGPL reference only | V [`technology/open-source-applications-evaluation.md`](../technology/open-source-applications-evaluation.md) F-C-04 | Needs a customer contract and credentials |
| 38 | Generated feeds for no-feed sites | **Defer** (Integrate when needed) | RSSHub 2026.11.25 (Node 26) | AGPL-3.0 | T [`experiments/repository-trials/rsshub.md`](../experiments/repository-trials/rsshub.md) | Unmodified, separate service; it returns 0 items on failure |
| 39 | Page change detection | **Defer** (Integrate when needed) | changedetection.io 0.70.4 | Apache-2.0 | T [`experiments/repository-trials/changedetection-io.md`](../experiments/repository-trials/changedetection-io.md) | `--prerelease=allow` needed |
| 40 | JS-page scraping | **Defer** | firecrawl / Playwright 1.65.2 / crawl4ai 0.9.6 | AGPL / Apache / Apache | D | DR-2: last resort |
| 41 | NRCS export (ninjs file drop), webhooks | **Defer** (designed) | own | — | I ADR-010 §7 | — |
| 42 | MOS / BXF / MAM | **Defer** | — | — | D `07_MULTIMEDIA…` §3 | — |
| 43 | Video tools (ffprobe, scene detection, black/freeze/silence, Groq Whisper) | **Defer** | ffmpeg, PySceneDetect, Groq API | LGPL/GPL builds vary; BSD-3; provider terms | T [`experiments/multimedia/results.md`](../experiments/multimedia/results.md) | Check ffmpeg build licence before shipping (CH = distribution) |
| 44 | Dedicated MT API | **Defer** | DeepL / Papago / Google | provider terms | BLOCKED-no-key (`06_AI…` §3) | — |
| 45 | Auth (local, static users, hashed tokens) | **Implement** | stdlib `hashlib.scrypt`, `secrets` | PSF | I ADR-009 | SSO is deferred |
| 46 | SecretStore (env / `.env`) | **Extend** | python-dotenv 1.2.4 | BSD-3 | T used in every experiment | Vault backend is deferred |
| 47 | Backup / restore / export / import / purge CLI | **Implement** | stdlib `sqlite3` `VACUUM INTO`, `json` | — | I `DATA_MODEL…` §4 stage 7 | — |
| 48 | SBOM and notices | **Adopt** (tool chosen at build) | CycloneDX or SPDX generator; pip-audit for vulnerabilities | — | I DR-14 | Not evaluated in phase 1 |
| 49 | Taranis AI, AIHOT, Horizon, OpenNews, worldmonitor, gdelt-pulse, feeds.fun, Huginn | **Reference only** | — | EUPL / MIT / MIT / none / AGPL / MIT / BSD-3 / MIT | V code reads | Copy no code from OpenNews or SHNRA (no licence); AGPL and EUPL: ideas only |
| 49b | Licence onboarding (DR-30 checklist, DR-17 attestation, valid_until kill switch, purge receipts) | **Implement** | own | — | I `08_LEGAL…` §13.5; ADR-010 §4 | Customer enters its own contract terms |
| 50 | n8n, SSPL components, no-licence repos | **Reject** | — | Sustainable Use / SSPL / none | V `08_LEGAL…` §7 | DR-14 |

**Count of custom programming (Implement rows):** 3, 9, 11, 12, 16, 18, 20, 23, 27, 28, 34, 35, 36, 45, 47, plus the
pages in row 25. Every Implement item is deterministic code except the prompts and validators in row 15. No row requires
local model inference.
