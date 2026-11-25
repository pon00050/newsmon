# Open-source complete applications: evaluation (R3, workstream C, applications half)

> **Status: Verified finding.** Evaluation of existing open-source applications; star counts and licences are dated 2026-11-25.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Date of every fact: **2026-11-25** unless stated. Registry of record: [`technology/applications-registry.csv`](applications-registry.csv)
(46 rows: the 13 leads, 2 extra Superdesk repos and 31 discovered). Trial logs: [`experiments/repository-trials/`](../experiments/repository-trials)`.
Code was read from shallow clones at the default-branch HEAD of 2026-11-25 (commits: worldmonitor d692bff, Horizon 098375a,
taranis-ai 469a802, miniflux b2058ff, FreshRSS 5d81cd8, changedetection.io c74be04, superdesk-core 68e6263, AIHOT fff6771,
OpenNews e57ee11, gdelt-pulse 7b20ca0, feeds.fun 6d9e7cc, huginn 4d4fa3f).

## D1 answer

**No open-source application is an adopt-directly MVP. Use the hybrid route (K-D): build a small core on our own,
use Taranis AI, AIHOT, OpenNews and Horizon as design references, and run RSSHub and changedetection.io beside it as
source adapters.** Taranis AI comes closest. It touches 8.5 of the 9 capabilities the MVP needs on the raw count, and about
**6 of 9 (two thirds) once adjusted for fit** (the matrix below shows the method). But adopting it means a seven-service Docker stack (Postgres,
Redis, Centrifugo, RQ workers, nginx). Its user experience is built for CSIRT teams, its default NLP models run locally
(models are mapped for English and German only, which breaks the cloud-only rule), it has nothing for Korean, and it is
licensed under EUPL-1.2. The second closest is AIHOT (MIT, 8 raw, about 6 of 9 fit-adjusted). It runs the right pipeline: collect, dedup,
LLM pre-filter and double scoring, event clustering, source-weighted "heat", publish. But it is two months old, its
prompts and UI are in Chinese, and it needs Postgres. The best fit in shape is OpenNews/Veriqen News: SQLite, TF-IDF
clustering, breaking-news detection that needs several independent sources, source health tracking, and no AI needed.
It has **no licence**, so it can be studied but not reused. The mature readers (miniflux, FreshRSS) do collection,
exact dedup, search and rules well. But neither has cross-source clustering or a desk triage queue. They score 6 of 9 on the
raw count, but the capabilities they lack (clustering, triage beyond regex or saved searches, AI) are the product's
core. That logic would end up in a sidecar anyway. Neither choice, adopting Taranis or extending a reader,
is faster than a purpose-built Python core (feeds, SQLite FTS5, hash and near-dup dedup, rules plus optional LLM,
webhooks) for an MVP of this size. **Evidence: INFERRED** from the code reads and two TESTED trials below.
**What would change this:** a requirement for multi-analyst report production with MISP or STIX sharing (that favours
forking Taranis), or a decision to accept Postgres plus Docker with Chinese-to-Korean prompt localisation (that makes
an AIHOT fork competitive).

## Capability matrix (closest candidates)

The capabilities come from the brief (continuous multi-source collection, dedup, search, triage and alerts) plus the
seat duties in public job advertisements (report feed breakage, summarise and translate,
archive). ● = present in code read, ◐ = partial, ○ = absent or not found. Tag: VERIFIED (code read) unless marked.

| Capability | Taranis AI | AIHOT | OpenNews | miniflux | FreshRSS | Horizon | Huginn | changedetection |
|---|---|---|---|---|---|---|---|---|
| 1 Continuous multi-source collection | ● RSS, web, Mastodon, MISP, RT | ● RSS, web lists, JSON, X, WeChat, push | ● RSS/Atom | ● feeds + scraper | ● feeds, WebSub | ◐ batch window (10 sources incl. GDELT, Telegram) | ● RSS/Website agents | ◐ per page |
| 2 Source-failure alerting (seat duty) | ◐ health endpoints | ◐ ops alerts module | ● per-source health | ◐ errors in UI | ◐ errors in UI | ○ | ◐ agent error events | ● per-watch error |
| 3 Persistent item archive | ● Postgres/SQLite | ● Postgres | ● SQLite | ● Postgres | ● SQLite/MySQL/PG | ○ Markdown files | ◐ event store | ◐ flat snapshots |
| 4 Exact dedup | ● hash(title, link, content) | ● | ● URL | ● per feed | ● GUID constraint | ● URL key | ● DeDuplication agent | ○ |
| 5 Near-dup / event clustering | ● fuzzy hash + LLM story bot | ● vectors or text fallback | ● TF-IDF | ○ | ○ | ◐ LLM topic merge | ○ | ○ |
| 6 Full-text search | ● (DOCUMENTED) | ◐ admin search (not verified) | ● keyword | ● Postgres FTS | ● boolean search | ◐ BM25 over digests | ○ | ○ |
| 7 Triage / priority rules | ● tags, wordlists, analyst workflow | ● LLM score + source tiers + heat | ◐ breaking flag | ◐ block/keep regex | ● filter actions | ● LLM profiles/thresholds | ● Trigger agent | ○ |
| 8 Alerts / delivery | ● publishers, presenters, API | ● site, notify | ◐ site | ● webhooks, 25 integrations, API | ◐ API, extensions | ● email, webhook, Pages | ● email, Slack, webhook | ● Apprise notifications |
| 9 AI summarise / translate | ● LLM (OpenAI-compatible) + local models | ● LLM (Chinese output) | ◐ extractive, optional Ollama | ○ | ○ (extensions) | ● | ○ | ○ (not checked) |
| **Count (● = 1, ◐ = ½)** | **8.5** | **8** | **7.5** | **6** | **6** | **5.5** | **5** | **3** |
| Licence | EUPL-1.2 | MIT | **none** | Apache-2.0 | AGPL-3.0 | MIT | MIT | Apache-2.0 |
| Runs here without Docker? | no (multi-service) | needs Postgres | Node + SQLite | needs Postgres | needs PHP | yes | Ruby + DB | **yes (TESTED)** |

The count measures breadth, not fit. Taranis's 8.5 includes features built for CSIRT intelligence products. AIHOT's 8
assumes Chinese prompts are acceptable. Fit-adjusted (Korean desk, no Docker, cloud-only AI, licence), the D1 paragraph
gives **about 6 of 9** for both. OpenNews's 7.5 counts for nothing in reuse terms because it has no licence. (The sums
were recomputed row by row after a first pass that undercounted three columns.)

## Per-candidate notes: the 13 leads

| # | Repo | Verdict | Evidence | Why |
|---|---|---|---|---|
| 1 | koala73/worldmonitor (91k★, AGPL) | Architectural reference | VERIFIED: `ARCHITECTURE.md`, `SELF_HOSTING.md`, `src/services/analysis-core.ts` | A geopolitical map dashboard over 1,381 source hosts. News is one panel, clustered by Jaccard similarity in a browser worker. State lives in an Upstash/Redis cache, not an archive. Self-hosting requires Docker or Podman. Open-core: Pro panels need a paid desktop key. It also runs ML in the browser (`@xenova/transformers`, `onnxruntime-web`). Worth reusing: its source list, feed-validation CI and velocity/convergence signals. |
| 2 | Thysrael/Horizon (15k★, MIT) | Architectural reference | VERIFIED: `src/orchestrator.py`, `src/processing/history.py`, `data/config.example.json` | A batch digest for a time window. Every item is scored by an LLM against a "profile" rubric. Dedup is a conservative URL key plus an LLM topic merge (union-find). Output goes to Markdown, email, webhooks and an MCP server. There is no item database: search is BM25 over past Markdown digests. Worth reusing: the profile and threshold model and the digest balancing. Not a continuous desk queue. |
| 3 | itheCreator1/newsintel | Reject (UNVERIFIED-absent) | `gh api` 404; user has 3 public repos, none named newsintel; `gh search repos newsintel` (15 results) shows none from this owner | Deleted, renamed or private. |
| 4 | spearb0lt/Self-Hosted-News-Research-Agent (0★) | Architectural reference | VERIFIED: README, `requirements.txt` | A ten-stage resumable pipeline (RSS, sitemaps, APIs, dedup, event grouping, digest) that runs in a 300-second serverless function. **No licence file.** Dedup uses a bundled local ONNX MiniLM, which breaks the cloud-only rule. No tests. |
| 5 | Ramrod72/OpenNews, "Veriqen News" (0★) | Architectural reference | VERIFIED: README, `prisma/schema.prisma` (sqlite), `src/lib/clustering/tfidf.ts`, `LICENSE` | The best match to the MVP's shape: RSS, SQLite, URL plus TF-IDF clustering, a "breaking" flag only when several independent sources publish within a window, per-source health, extractive summaries, 108 test files. **`LICENSE` reads "LICENSE PLACEHOLDER … does not yet have a license applied"**, so no reuse rights. Two months old, 2 contributors. Study its algorithms and write our own. |
| 6 | UnbubbleHub/gdelt-pulse (7★, MIT) | Architectural reference | VERIFIED: README, `pyproject.toml` | GDELT only. Ingests every 15 minutes, normalises and dedups, embeds, and clusters with cosine similarity plus entity overlap. Hybrid pgvector and Postgres FTS search merged by RRF. Embeddings use `fastembed` (local ONNX), which breaks the cloud-only rule; swap to OpenAI embeddings. Reference for D4/D5 (R6). |
| 7 | FreshRSS/FreshRSS (16.7k★, AGPL) | Integrate as component | DOCUMENTED + code read (`app/Models/FilterAction.php`, `BooleanSearch.php`, `EntryDAO.php`) | Mature, with releases (1.31.0 on 2026-11-23), 477 contributors and SQLite support. Filter actions run saved boolean searches that auto-mark items read, starred or labelled. GReader and Fever APIs, WebSub, extensions. Dedup is per feed (a GUID unique constraint); there is no cross-source dedup or clustering. Needs PHP, which this machine lacks, so not trialled. |
| 8 | miniflux/v2 (10k★, Apache-2.0) | Integrate as component | VERIFIED: `internal/reader/filter`, `internal/reader/fetcher/request_builder.go`, `internal/config/options.go` | A Go single binary, but **PostgreSQL only**. Block and keep regex rules, a REST API, webhooks and many integrations. `FETCHER_ALLOW_PRIVATE_NETWORKS` defaults to `false`: a dialer-level check refuses private hosts, which is good SSRF hygiene. No clustering. A good reader UI if the team wants one, not the core. |
| 9 | DIYgod/RSSHub (47k★, AGPL) | Integrate as component | **TESTED**: [`experiments/repository-trials/rsshub.md`](../experiments/repository-trials/rsshub.md) | Runs as an npm library **on Node 26 only**: 116 Yonhap items via `/yna/en/national`. On Node 22 it fails with `Temporal is not defined`. **It returns 0 items rather than an error** on failure. The `yna` route fetches every article page. Route namespaces include `apnews`, `reuters`, `yna`, `kbs`, `koreaherald`, `naver`, `daum`, `whitehouse`, `un`, `nhk`. |
| 10 | huginn/huginn (50.6k★, MIT) | Architectural reference | DOCUMENTED + code read (`app/models/agents/`, 74 agents) | Has the whole alert chain as agents (RSS, Website, DeDuplication, Trigger, Digest, Email/Slack/Webhook), but no archive search or clustering. A Rails plus MySQL/Postgres stack, off the project's Python path. Its DeDuplication and Trigger agents are the reference for the rule chain. |
| 11 | dgtlmoon/changedetection.io (36k★, Apache-2.0) | Integrate as component | **TESTED**: [`experiments/repository-trials/changedetection-io.md`](../experiments/repository-trials/changedetection-io.md) | pip install without Docker works, but only with `--prerelease=allow` (otherwise you silently get the old 0.45.14). The REST API created a watch, fetched it and stored a snapshot. The private-address guard blocked 127.0.0.1 and 169.254.169.254 at fetch time. Use it for pages that have no feed (briefing indexes, notices). |
| 12 | superdesk/superdesk-core (AGPL) (+ superdesk, superdesk-planning: Reject) | Architectural reference | VERIFIED: `superdesk/io/feeding_services/` (ap, ap_media, ftp, email, http, rss, ritzau, bbc_ldrs), `superdesk/io/feed_parsers/` (ANPA, AP ANPA, AP Media, NewsML 1.2/2.0, NITF, IPTC7901, ninjs, and others), `setup.py` | The only candidate with **wire-agency ingest**: an AP Media API client (`https://api.ap.org/media/v/content/feed`) and parsers for agency formats. It needs MongoDB, Elasticsearch, Redis and Celery, so the whole CMS is out of scope. "reuters" matched nothing under `superdesk/io` (UNVERIFIED-absent). Reference for the day AP or Reuters access exists, which is BLOCKED-no-key now. |
| 13 | firecrawl/firecrawl (209k★, AGPL) | Integrate as component (optional) | DOCUMENTED | A scrape and extract API. Self-hosting needs Docker, Redis and a Playwright service; the cloud API is paid. It overlaps trafilatura (R4). Use it only for hard JavaScript pages. |

## Per-candidate notes: discovered set (serious candidates)

| Repo | Verdict | Evidence | Note |
|---|---|---|---|
| taranis-ai/taranis-ai (1.2k★, EUPL-1.2, 37 contributors, release 1.5.3 on 2026-11-06) | **Extend or fork** (the only one) | VERIFIED: README, `src/worker/worker/{collectors,bots}`, `src/core/core/model/news_item.py`, `src/core/core/config.py`, `supported_languages.json` | Collectors: RSS, simple web, Playwright, Mastodon, MISP, RT. Dedup: a unique `hash` plus a `fuzzy_hash` (fuzzbite, bodies of 256 bytes or more) with collection matching. Bots: story clustering (via the `taranis-llm-bot` package and an OpenAI-compatible endpoint), grouping, tagging, wordlist, summary, NER, sentiment, IoC. Analyst report items, PDF presenters, publishers, an OpenAPI REST API. The default NLP model map is **local Hugging Face models for en/de only** (bart-large-cnn, flair NER, multilingual MiniLM); "16 GB RAM with NLP". Postgres is primary, SQLite is supported. No SSRF guard found (grep for `is_private`/`is_global`/`SSRF` in the worker: none, UNVERIFIED-absent). Not trialled: no Docker. |
| KKKKhazix/AIHOT (11.4k★, MIT, created 2026-09-28) | Architectural reference | VERIFIED: README, `.env.example`, `docker-compose.yml`, `database/migrations/` | The pipeline we would design (dedup, pre-filter, two independent LLM scores, per-source-tier thresholds, event clustering by vector or text fallback, heat counted per independent source over 48 hours with a 24-hour half-life), with a `MODEL_CALLS_ENABLED`/`COLLECT_ENABLED` kill switch and per-step model overrides. Needs Postgres 17. Prompts and UI are in Chinese. 170 test files. Too young to adopt; copy its algorithms (MIT). |
| Tiendil/feeds.fun (400★, BSD-3) | Architectural reference | DOCUMENTED + `LICENSE` read | An LLM assigns tags, then user rules score news by tags. This is the cleanest model for desk triage that still works with AI off (rules over tags). Postgres; 1 contributor. |
| mediacloud/story-indexer (Apache-2.0) | Architectural reference | DOCUMENTED | Media Cloud's research-scale indexing pipeline (RabbitMQ, Elasticsearch). The old `mediacloud/backend` is archived (Reject). |
| internetarchive/newsum (AGPL) | Architectural reference (for R8) | DOCUMENTED | Daily summaries of TV news transcripts. |
| superdesk/newsroom (GPL-3.0) | Architectural reference (only if D3 = client service) | DOCUMENTED | A client-facing wire portal. |
| n8n, Node-RED, Activepieces, Windmill | Reject | DOCUMENTED (licence files read for n8n, Activepieces, Windmill) | Workflow glue with no news-domain capability. n8n's Sustainable Use License restricts commercial offering to third parties. Activepieces is MIT core plus proprietary `ee/`. Windmill is AGPL plus proprietary EE. A Python scheduler does the MVP's glue more cheaply. |
| tt-rss, CommaFeed, NewsBlur, yarr, Glance, fusion, newspipe, Folo | Reject | DOCUMENTED | Readers or dashboards that add nothing over miniflux/FreshRSS (reasons per row in the CSV). |
| SK-CERT/Taranis-NG, KoreaNewsCrawler, auritus, agendascope, morningdeck, scoop, Global-News-Intel-Platform, orodruin, hacker-news-digest, news-please, RSS-to-Telegram-Bot, nats-news-analysis | Reject | DOCUMENTED | Superseded, archived, stale, single-site, unlicensed or toy scale (reasons per row in the CSV). |

**Korean-language applications: UNVERIFIED-absent.** Searches run: `gh search repos "뉴스 모니터링"` (only 0-star
personal or company scripts), `"korean news crawler"` (KoreaNewsCrawler, a Naver scraper last pushed 2024-04), plus the topic
searches below. No maintained Korean news-monitoring application was found.

**Discovery searches run (2026-11-25):** `gh search repos` keyword queries ("news intelligence platform", "media
monitoring", "news clustering events", "news monitoring dashboard", "taranis", "korean news crawler", "뉴스 모니터링",
"news event detection", "mediacloud", "news-please", "superdesk", "newsroom wire", "ap reuters", "kagi news", "yarr rss",
"news digest llm"), plus topic queries (news-aggregator, rss-reader, osint, media-monitoring, news-analysis,
feed-reader, news-clustering, workflow-automation, rss-aggregator, gdelt, event-detection). Six multi-word keyword
queries returned nothing (for example "news aggregator self-hosted", "OSINT news analysis"), because `gh` ANDs terms
over name and description. The topic queries filled that gap. Raw outputs are in the R3 scratch folder, not the project.

## Trials

| Candidate | Result | Log |
|---|---|---|
| changedetection.io 0.70.4 | **Worked** (pip, Python 3.13, no Docker); API and SSRF guard confirmed | [`experiments/repository-trials/changedetection-io.md`](../experiments/repository-trials/changedetection-io.md) |
| RSSHub 2026.11.25 (npm library) | **Worked on Node 26.13.1**, failed on Node 22.16 | [`experiments/repository-trials/rsshub.md`](../experiments/repository-trials/rsshub.md) |

Not trialled, with reasons: Taranis AI, worldmonitor, AIHOT, gdelt-pulse, miniflux, NewsBlur and Superdesk all need
Docker or Postgres/Mongo, which this machine lacks. FreshRSS and tt-rss need PHP, which is absent. OpenNews and SHNRA
have no licence, so a trial would not change their verdict. Horizon would install, but a trial costs LLM spend and
cannot move its verdict (it is batch-only by design), so it is offered for round 2.

## Security and licence notes for the architecture (S1)

- **SSRF:** miniflux (private networks refused by default; VERIFIED) and changedetection.io (fetch-time block; TESTED)
  get this right. No equivalent guard was found in Taranis's worker. Any fetcher we write must resolve the host and
  refuse private ranges at connect time, not only at URL-validation time.
- **Silent nulls:** RSSHub returns an empty feed on failure (TESTED). A collector must record the HTTP status per run
  and alert on "0 items + error". This is also the seat's "tell the wire service or engineering when a feed breaks" duty.
- **Licences:** AGPL (RSSHub, FreshRSS, firecrawl, worldmonitor, Superdesk) is safe as an unmodified separate service.
  Modifying one and offering it over a network brings source-disclosure duties. EUPL-1.2 (Taranis) is copyleft, and
  its definition of distribution covers network access. MIT, BSD or Apache code can be copied (Horizon, AIHOT, feeds.fun,
  miniflux, changedetection, Huginn). Unlicensed repos (OpenNews, SHNRA) cannot be copied. R9 to confirm.
- **Compute policy:** Taranis (default NLP), gdelt-pulse (fastembed), SHNRA (ONNX MiniLM) and worldmonitor (in-browser
  transformers.js) carry local inference. Any reuse must swap it for cloud APIs.

## Findings

### F-C-01 · No application is adoptable as the MVP; the hybrid route (K-D) is fastest
- Question: does an existing app cover most of collection → dedup → search → triage/alerts?
- Finding: the closest (Taranis AI) covers about 6 of 9 needed capabilities after fit adjustment, behind a seven-service Docker stack, CSIRT UX, local default NLP and EUPL. No candidate combines a reusable licence, a light deployment and cross-source clustering.
- Evidence: INFERRED from the VERIFIED code reads above and the two TESTED trials (2026-11-25).
- Limits: Taranis was not run; its search and alerting are DOCUMENTED, not tested.
- Implication: build a small Python core and copy algorithms from MIT/BSD references; run RSSHub and changedetection.io as optional adapters.
- Open: a round-2 Taranis trial on a Docker-capable host would firm up "Extend or fork" against "reference".

### F-C-02 · RSSHub reports failure as an empty feed
- Evidence: TESTED, private experiment data (not published), `run_node26.txt`.
- Implication: collectors need explicit per-run status, and "0 items" must never be read as "no news".

### F-C-03 · changedetection.io runs without Docker and blocks private addresses
- Evidence: TESTED, private experiment data (not published).
- Limits: needs `--prerelease=allow`; uses Flask's dev server in pip mode.

### F-C-04 · Superdesk is the only open-source source of AP Media API and agency-format parsers
- Evidence: VERIFIED, `superdesk/io/feeding_services/ap_media.py`, `superdesk/io/feed_parsers/`.
- Implication: when wire access exists, port or reference these parsers (AGPL: reference rather than copy, unless the AGPL terms are accepted).

API spend by R3: **$0** (no model calls).
