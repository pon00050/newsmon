# ADR-001 · Foundation strategy (D1): hybrid K-D, built as a library-assembled core (K-B) with optional out-of-process adapters

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: Python core built; optional adapters (changedetection.io, RSSHub) not built.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25). Reviewer: V1.
- **Decision owner:** project owner. **Informs:** deliverables 10, 11, 12.

## Context

The project brief (Workstream K) asks for a comparison of four
strategies:

| ID | Strategy |
|---|---|
| K-A | Adopt and extend one existing open-source application |
| K-B | Assemble independently maintained libraries into a lightweight application |
| K-C | Integrate several existing applications through APIs and shared data |
| K-D | Hybrid: existing collection infrastructure plus custom intelligence processing |

Constraints from phase 1: no Docker on this machine ([`decision-log.md`](../../decision-log.md) P-004); no local model inference (project policy);
proprietary core must stay free of AGPL/SSPL/fair-code code to keep all three deployment models open
([`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §9(a), DR-14); KO/ZH text must be searchable
([`experiments/korean-fts/results.md`](../../experiments/korean-fts/results.md)).

## Options considered

| Option | Best candidate | For | Against | Evidence |
|---|---|---|---|---|
| **K-A** adopt | Taranis AI 1.5.3 (EUPL-1.2) | Widest coverage: 8.5/9 raw, about 6/9 fit-adjusted; story clustering, analyst workflow, REST API | Seven-service Docker stack (Postgres, Redis, Centrifugo, RQ, nginx); default NLP is local Hugging Face models for en/de only (breaks no-local-inference policy); CSIRT UX; no Korean; EUPL copyleft covers network access; no SSRF guard found; not trialled | VERIFIED code read, [`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) (Taranis row, F-C-01) |
| K-A alt | AIHOT (MIT) | Right pipeline shape (dedup, LLM pre-filter, double scoring, clustering, source-weighted heat, kill switches) | Two months old, Chinese prompts and UI, Postgres 17 | same file, AIHOT row |
| K-A alt | miniflux / FreshRSS | Mature collection, exact dedup, search, rules | No cross-source clustering, no triage queue, no AI; miniflux is Postgres-only, FreshRSS is AGPL + PHP | same file, rows 7–8 |
| **K-B** assemble | feedparser, httpx, trafilatura, courlan, datasketch, SQLite FTS5, APScheduler, apprise, FastAPI | Every text stage has a maintained permissive library; the chain ran end to end on BBC and Yonhap | All glue, the queue, the rules and the UI are ours to write | TESTED, [`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) §1, `experiments/component-smoke/results.json` (raw results not published: they contain third-party article snippets) |
| **K-C** integrate apps | miniflux (collection) + changedetection.io (pages) + RSSHub (generated feeds) + Huginn (rules/alerts) + custom clustering sidecar | Each piece mature | Four runtimes (Go+Postgres, Python, Node 26, Ruby+DB) and four data stores; the product core (clustering, triage, AI, licence gating) still lives in a custom sidecar; licence flags would have to be enforced across apps that do not know them | INFERRED from the per-app rows in [`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md); RSSHub Node-26-only TESTED ([`experiments/repository-trials/rsshub.md`](../../experiments/repository-trials/rsshub.md)) |
| **K-D** hybrid | Custom Python core for intelligence; collection from libraries plus, where a source has no feed, changedetection.io or self-hosted RSSHub run as separate services behind an adapter interface | Keeps one data model and one licence gate; adapters stay optional and process-isolated (AGPL boundary) | Adapter services add operations when switched on | R3's D1 answer ([`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) "D1 answer"); R4's spine ([`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) §1) |

### Reconciling R3 and R4

R3 recommends **K-D**; R4 concludes **K-B is technically sufficient**. These are not in conflict once the time axis is
explicit: R4 shows the *core* can be assembled from libraries; R3 shows that some *sources* (pages without feeds) are
best served by existing apps. The MVP source set (ADR-002) needs no adapter: all recommended sources are native RSS/Atom or
keyless JSON APIs ([`sources-and-licensing/information-source-and-api-registry.md`](../../sources-and-licensing/information-source-and-api-registry.md) §2). So the MVP ships as K-B, with the adapter
interface present and **no adapter service enabled by default**. That is K-D in its lightest form.

## Decision

**K-D, implemented at MVP time as a K-B core.** One Python process (web + in-process scheduler) over one SQLite file.
Collection uses `feedparser` + `httpx` behind a `SourceAdapter` interface with three adapter kinds:

1. `feed` (RSS/Atom/JSON API, in-process): MVP.
2. `changedetection` (talks to a separately run changedetection.io over its REST API): interface specified, off by default.
3. `rsshub` (fetches a self-hosted RSSHub route over HTTP): interface specified, off by default.

Algorithms are reimplemented from MIT/BSD references where useful (AIHOT's heat and kill switch, Horizon's profile
thresholds, feeds.fun's rules-over-tags); nothing is copied from no-licence repos (OpenNews, SHNRA) or AGPL code.

### Sub-decision: `reader` vs `feedparser` + `httpx` (R4 recommended `reader`)

R4 picked `reader` 3.27 as the ingest spine (TESTED, `component_smoke/results.json`). S1 chooses its runner-up,
`feedparser` 6.0.14 + `httpx` 0.28.1 with our own `feed`/`fetch_run` tables, because:
- R6's data model needs a `fetch_run` row per attempt with HTTP status and error class, which drives feed health and the
  "200 but 0 entries" alarm ([`technology/data-model-and-lifecycle.md`](../../technology/data-model-and-lifecycle.md) §4; RSSHub silent-null lesson,
  [`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) F-C-02). `reader` keeps its own schema, so we would run two schemas.
- `reader` has no public user-agent argument and ships a `.ua_fallback` plugin that retries a 403 with another UA, which
  the access-ethics rule forbids ([`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) F-C-01).
- The SSRF guard must sit at connect time in our HTTP client ([`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) "Security and licence notes").
- Conditional GET via `feedparser.parse(etag=, modified=)` is TESTED ([`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) F-C-02).
This is INFERRED; reversing it costs about one task.

## Consequences

- One runtime (Python 3.12+; 3.13.7 used in phase 1), one data store, one licence gate, one place for tenant scoping.
- We write the queue, rules, digest and UI ourselves (deliverable 10 lists each as Implement).
- No AGPL code is linked into the core; RSSHub and Firecrawl, if ever used, run unmodified as separate services
  (DR-14; [`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §9(a)).
- Taranis remains the fallback if requirements move toward multi-analyst intelligence production.

## Evidence

[`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) (D1 answer, matrix, F-C-01…04) ·
[`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) (§1, F-C-01, F-C-02, F-C-07) ·
[`experiments/repository-trials/`](../../experiments/repository-trials) (RSSHub, changedetection.io TRIAL.md) ·
[`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §7, §9(a) · [`technology/open-source-technology-evaluation.md`](../../technology/open-source-technology-evaluation.md).

## Reversal triggers

- A requirement for multi-analyst report production with MISP/STIX sharing → re-evaluate forking Taranis (R3).
- Acceptance of Postgres + Docker and a Chinese→Korean prompt localisation effort → an AIHOT fork becomes competitive (R3).
- More than ~20% of wanted sources lack feeds → enable the changedetection.io/RSSHub adapters (still K-D).
- A Taranis trial on a Docker-capable host (round-2 offer) showing its clustering and queue fit a Korean desk with cloud
  models swapped in.
