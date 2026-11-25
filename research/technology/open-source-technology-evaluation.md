# 03 · Open-source technology evaluation (S1 synthesis of R3 and R4, 2026-11-25)

> **Status: Experimental result.** Deliverable 03. Synthesis of repository trials and component smoke tests.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Decision informed:** D1 (ADR-001), with inputs to D4 and D8.

**Sources merged:**

| What | Where |
|---|---|
| R3, complete applications | [`technology/open-source-applications-evaluation.md`](open-source-applications-evaluation.md); registry [`technology/applications-registry.csv`](applications-registry.csv) (46 rows); trials in [`experiments/repository-trials/`](../experiments/repository-trials) |
| R4, libraries and MCP | [`technology/open-source-components-evaluation.md`](open-source-components-evaluation.md), [`technology/mcp-servers-evaluation.md`](mcp-servers-evaluation.md); registry [`technology/components-registry.csv`](components-registry.csv) (60 rows); smoke test in [`experiments/component-smoke/`](../experiments/component-smoke) |
| Licences | [`sources-and-licensing/oss-licenses.csv`](../sources-and-licensing/oss-licenses.csv) and [`sources-and-licensing/legal-and-licensing-report.md`](../sources-and-licensing/legal-and-licensing-report.md) §7, §9(a) |

This file does not repeat those reports. It merges them into one matrix, reconciles where they disagree, and gives the
verdicts used in deliverables 10 and 11. All facts date from 2026-11-25.

## 1. Answer

No open-source application can be adopted directly as the MVP. The fastest defensible route is **K-D**: a small Python
core assembled from permissively licensed libraries, with two existing applications kept as optional adapters that run
outside the process. Those two are changedetection.io (Apache-2.0, TESTED without Docker) and a self-hosted RSSHub
(AGPL-3.0, TESTED on Node 26).

The MVP ships with both adapters switched off, because the recommended sources all have native feeds. In practice, then,
the MVP is **K-B**.

Evidence: INFERRED from the VERIFIED code reads, the two TESTED application trials and the TESTED library chain. See
ADR-001.

## 2. Comparative matrix: complete applications

These are the closest candidates. Capability counts are R3's (● = 1, ◐ = ½, across 9 capabilities). "Fit" is R3's
adjustment for a Korean desk with no Docker, cloud-only AI and a reusable licence.

| Candidate | Licence | Raw / fit | Deployment weight | Compute-policy fit | Evidence | Verdict | Role here |
|---|---|---|---|---|---|---|---|
| Taranis AI 1.5.3 | EUPL-1.2 | 8.5 / ~6 | 7 services, Docker | ✗ default local HF NLP (en/de) | V code read | Reference (fallback fork target) | Reversal trigger in ADR-001 |
| AIHOT | MIT | 8 / ~6 | Postgres 17 | ✓ (cloud LLM) | V | Reference: copy algorithms | Heat, kill switches, per-step model overrides |
| OpenNews / Veriqen | **none** | 7.5 / 0 reuse | Node + SQLite | ✓ | V (`LICENSE` placeholder) | Study only, copy nothing | Multi-source "breaking" rule, source health |
| miniflux v2 | Apache-2.0 | 6 | Go + Postgres-only | ✓ | V | Reference | SSRF dialer pattern; regex rules |
| FreshRSS 1.31.0 | AGPL-3.0 | 6 | PHP | ✓ | D + code read | Reject for core | — |
| Horizon | MIT | 5.5 | none | ✓ (cloud LLM) | V | Reference | Profile/threshold model; digest balancing |
| Huginn | MIT | 5 | Rails + DB | ✓ | D + code read | Reference | DeDuplication/Trigger agent chain |
| changedetection.io 0.70.4 | Apache-2.0 | 3 | pip, no Docker | ✓ | **T** | **Integrate (optional adapter)** | Pages without feeds |
| RSSHub 2026.11.25 | AGPL-3.0 | n/a | Node 26 only | ✓ | **T** (silent 0 items on failure) | **Integrate (optional, unmodified, separate)** | Generated feeds |
| Superdesk core | AGPL-3.0 | n/a | Mongo + ES + Redis + Celery | ✓ | V | Reference for wire parsers | AP Media API client and NewsML/NITF/ANPA parsers (ADR-010) |
| worldmonitor | AGPL-3.0 | n/a | Docker/Podman, Redis | ✗ in-browser transformers.js | V | Reference | Source list, velocity signals |
| gdelt-pulse | MIT | n/a | Postgres + pgvector | ✗ fastembed | V | Reference | GDELT ingest + RRF hybrid search |
| feeds.fun | BSD-3 | n/a | Postgres | ✓ | D | Reference | Rules over tags with AI off |
| n8n / Activepieces / Windmill / Node-RED | Sustainable Use / MIT+EE / AGPL+EE / Apache | n/a | platforms | — | D | Reject | n8n blocked in all three commercial models (`08_LEGAL…` §9(a)) |
| SHNRA, itheCreator1/newsintel | none / 404 | — | — | ✗ ONNX MiniLM | V | Reject | — |

## 3. Comparative matrix: libraries and services by pipeline stage

| Stage | Chosen | Runner-up / rejected | Licence (chosen) | Evidence | Verdict |
|---|---|---|---|---|---|
| Feed parsing | feedparser 6.0.14 | fastfeedparser (no ETag), atoma (bytes only) | BSD-2 | T | Adopt |
| Feed ingest and state | own tables + httpx 0.28.1 | **reader 3.27** (R4's pick) | BSD-3 | T | Extend httpx; reader not used (§4.1) |
| Extraction | trafilatura 2.4.0 | readability-lxml; newspaper4k (fails on Korean without nltk); goose3 (0 chars Korean); news-please (archived) | Apache-2.0 | T (n=1 per site) | Adopt, gated by licence flags |
| URL canonicalisation | courlan 1.5.0 | hand rules | Apache-2.0 | T | Extend |
| Near-dup | datasketch 2.0.0 | simhash (stale; 45% recall on rewrites) | MIT | T (R4 smoke + R6 experiment) | Adopt |
| Title similarity | — (not needed) | rapidfuzz 3.14.6 | MIT | T | Defer |
| Language ID | script ratio | py3langid, langdetect; fasttext-langdetect (local model ✗) | — | T | Implement |
| KO/ZH search | FTS5 + CJK bigram pre-tokenisation | trigram + LIKE; unicode61 ✗; jieba (0.91 recall); kiwipiepy (policy gray area); konlpy (GPL, stale) | public domain | T (`korean_fts/RESULTS.md`) | Implement on Adopt |
| Storage | SQLite 3.50.4 WAL | PostgreSQL + pgvector (later); OpenSearch; Meilisearch (BUSL EE files); Typesense (GPL) | public domain | T | Adopt |
| Vectors | in-memory centroids | sqlite-vec 0.1.9 (pre-1.0) | — | T | Defer sqlite-vec |
| Clustering | own incremental + scikit-learn TF-IDF | HDBSCAN, BERTopic (local model ✗), river | BSD-3 | T | Implement + Adopt |
| Scheduler | APScheduler 3.11.3 | huey, RQ/Celery (brokers), Prefect/Dagster (platforms) | MIT | T | Adopt |
| Web/API | FastAPI 0.165.0 + Jinja2 + htmx 4.0.2 | Datasette (read-only), Streamlit | MIT / BSD-3 / 0BSD | D (FastAPI, htmx metadata) | Adopt |
| Notifications | smtplib; apprise 2.3.0 later | direct Telegram/Slack | PSF / BSD-2 | T parse-only | Adopt / Defer |
| MCP | custom server on the official Python SDK | **datasette-mcp** (R4's first pick), database-mcp-sqlite | MIT (verify) | D | Extend (§4.2) |
| External GDELT MCP | — | cyanheads/gdelt-mcp-server | Apache-2.0 | V metadata | Defer (user-side tool, optional) |
| Hosted RSS/news MCP servers | — | ~20 registry entries | mostly closed | V | Reject (fetching from a stranger's IP and UA) |

## 4. Reconciled conflicts

### 4.1 `reader` (R4) vs `feedparser` + `httpx` with our own tables

R4 recommended `reader` as the ingest spine (TESTED, F-C-01). S1 uses R4's runner-up instead, for four reasons:

- one schema instead of two;
- a `fetch_run` row on every attempt, which feed health needs (R6 lifecycle §4; R3 F-C-02);
- a fixed descriptive UA, with no 403-retry-with-another-UA plugin;
- the connect-time SSRF guard sits in our own client.

Both options rest on TESTED components, and switching between them is about one task of work. ADR-001.

### 4.2 `datasette-mcp` (R4) vs a narrow custom MCP server (R7)

`execute_sql` would expose every row, including text that `DisplayPolicy` must withhold (DR-3), and it returns untrusted
text without trust labels. R7's narrow read-only tools win for the product. Datasette stays an optional operator tool,
run against a read-only copy. ADR-008.

### 4.3 K-D (R3) vs K-B (R4)

These describe the same design at different points in time: K-B is the core, and K-D adds adapters when sources need them.
ADR-001.

### 4.4 Taranis: "Extend or fork" (R3's row verdict) vs not chosen

R3 rates Taranis as the only extend-or-fork candidate. Its own D1 answer still recommends K-D, because of Docker, local
NLP, Korean support and EUPL. S1 keeps Taranis as the named fallback, with a round-2 trial on a Docker-capable host as the
test that would firm this up.

### 4.5 Embeddings (R7: "no vector store") vs R6 (embeddings needed for clustering)

Embeddings are adopted for clustering only. They are not used for search or RAG. ADR-005.

### 4.6 kiwipiepy (R4: gray area) vs FTS5 bigram (R6)

The bigram method reached recall 1.00 without kiwipiepy, so kiwipiepy is not a dependency. Bringing it in remains a user
decision under the no-local-inference policy.

### 4.7 Supplement 02 connectors

No open-source connector for AP Media Agent output or Reuters Connect was found other than Superdesk's (AGPL, heavy).
The directory watcher and the wire parsers are therefore Implement, with Superdesk as a read-only reference. ADR-010.

## 5. Licence posture (from `08_LEGAL…` §7, §9(a))

- **Core dependencies are permissive only**: MIT, BSD, Apache-2.0, PSF, 0BSD or public domain. That keeps
  customer-hosted shipping (which counts as conveying), managed private and SaaS all open.
- **AGPL tools** (RSSHub, Firecrawl, FreshRSS, Superdesk, worldmonitor) run only unmodified, as separate services, or
  serve as references.
- **n8n, SSPL and no-licence repos** are rejected.
- **EUPL-1.2 (Taranis)** is copyleft that reaches network use, so it is not used.
- **An SBOM and a notices bundle are produced from day one** (DR-14).

## 6. What phase 1 did not establish

- Taranis, AIHOT, miniflux and Superdesk were not run (no Docker or Postgres here).
- FastAPI and htmx were registry metadata only; they were not run.
- The MCP SDK version and defusedxml were not evaluated.
- Korean-language open-source applications were UNVERIFIED-absent ([`technology/open-source-applications-evaluation.md`](open-source-applications-evaluation.md), searches listed there).
- Extraction quality rests on one page per site.
