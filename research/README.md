# Newsmon research library

> **Status: Historical decision (index).** This page is an index and reading guide. Each document carries its own status line.

Newsmon is a local news-monitoring tool for a foreign-news desk. This folder is the research it was built from: the
business and legal evidence, the experiments, the architecture decisions and the full MVP specification. The software
itself is in the parent folder. **Release A + A.1, extended by version 0.2.0, is what is built.** It collects authorised RSS/Atom feeds and customer
wire files from a watched folder, normalises and deduplicates them, ranks them with profile rules, and shows a
searchable queue on a loopback web page. AI assessment of selected articles is optional, off by default, and limited to
sources whose licence flags permit it. Version 0.2.0 (2026-11-27) added editorial verdicts and a shift report, in-app
alerts, a local ffmpeg check of wire video clips with an ingest sheet, and saved searches; see the
[changelog](../CHANGELOG.md). Event grouping, e-mail alerts and digests, a JSON API, MCP, authentication, backup and
speech or AI video analysis are specified here but **not built**.

## Status legend

Every published document begins with one of these labels.

| Label | Meaning |
|---|---|
| **Verified finding** | Checked against a primary source (official documentation, statute text, an API response, source code) on the date given. Individual rows carry evidence tags; items marked UNVERIFIED stay unverified. |
| **Experimental result** | Measured by running something in this project. Samples are small; treat as indicative. |
| **Estimate** | Based on documentation, inference or sizing, without a direct test. |
| **Design proposal (not built)** | A specification, architecture or backlog item. Most of the full MVP is in this class. |
| **Historical decision** | A decision, review or synthesis that records how the project reached its current state. Where it disagrees with the code or the decision log, those win. |
| **Implemented (Release A + A.1)** | Describes software that exists and was tested. |

Evidence tags used inside documents (TESTED, VERIFIED, DOCUMENTED, INFERRED, UNVERIFIED, REJECTED) are defined in
[evidence-conventions.md](evidence-conventions.md).

## Which document wins

When two documents disagree, the higher one is right.

| Rank | Source | Use it for |
|---|---|---|
| 1 | [decision-log.md](decision-log.md), rows P-011, P-013 and P-015 | the scope of what is built and why |
| 2 | the application code, tests and `config.example/` in the parent folder | actual behaviour |
| 3 | the application README and the generated `PROGRESS.md` | how to run it and its state |
| 4 | other decision-log rows | process history |
| 5 | [architecture/adr/](architecture/adr/) | the reasoning behind design choices; the build state of each is in the decision log |
| 6 | [specification/](specification/), [architecture/recommended-architecture.md](architecture/recommended-architecture.md), [architecture/build-vs-reuse-matrix.md](architecture/build-vs-reuse-matrix.md) | the full MVP, as a future reference |
| 7 | business, sources-and-licensing, technology and experiments | evidence |
| 8 | [reviews/consolidated-research-synthesis.md](reviews/consolidated-research-synthesis.md), [reviews/review-v1.md](reviews/review-v1.md) | history of the research round |

Known places where a lower-ranked document says something the code does not do:

- The specification and ADR-002 / ADR-006 let public feeds go to an external AI model. The shipped configuration sends
  nothing from public feeds (`permitted_ops: []`) until an operator changes a source's flags (decision log P-013).
- The specification names APScheduler, trafilatura, scikit-learn and htmx. None is used (decision log P-015).
- Cost per assessed article appears as $0.0013 (research estimate) and about $0.0003 (nine live calls). The second is
  the measured one; both come from a price table, not a billing meter.

## Reading paths

**Business analyst**

1. [business/industry-and-business-process-report.md](business/industry-and-business-process-report.md): the desk, its duties and the evidence base.
2. [business/desk-workflows.md](business/desk-workflows.md) and [business/desk-practices.md](business/desk-practices.md): how the work is done.
3. [business/commercial-product-landscape.md](business/commercial-product-landscape.md): what can be bought today.
4. [business/broadcaster-licensing-evidence.md](business/broadcaster-licensing-evidence.md): who holds wire access.
5. [architecture/adr/ADR-003-mvp-user-and-use-case.md](architecture/adr/ADR-003-mvp-user-and-use-case.md): the chosen user and the two commercial models.
6. [reviews/consolidated-research-synthesis.md](reviews/consolidated-research-synthesis.md): the whole round in one page.

**Engineer**

1. [decision-log.md](decision-log.md): what is built and why.
2. [architecture/recommended-architecture.md](architecture/recommended-architecture.md) and the [ADRs](architecture/adr/).
3. [technology/open-source-technology-evaluation.md](technology/open-source-technology-evaluation.md) and [architecture/build-vs-reuse-matrix.md](architecture/build-vs-reuse-matrix.md).
4. [experiments/](experiments/): deduplication, event clustering, Korean full-text search, AI processing.
5. [technology/ai-threat-model.md](technology/ai-threat-model.md) and [technology/reliability-and-security.md](technology/reliability-and-security.md).
6. [reviews/round3-review.md](reviews/round3-review.md): review of the implemented code.
7. [specification/](specification/): the full target, not the current state.

**Licensing**

1. [sources-and-licensing/legal-and-licensing-report.md](sources-and-licensing/legal-and-licensing-report.md): constraints and deployment models. Research notes, not legal advice.
2. [sources-and-licensing/source-registry.csv](sources-and-licensing/source-registry.csv) and [sources-and-licensing/information-source-and-api-registry.md](sources-and-licensing/information-source-and-api-registry.md): per-source terms and flags.
3. [sources-and-licensing/oss-licenses.csv](sources-and-licensing/oss-licenses.csv): licence scope of candidate open-source components.
4. [sources-and-licensing/statute-extracts.md](sources-and-licensing/statute-extracts.md): statute text that was relied on.
5. [architecture/adr/ADR-002-mvp-source-set.md](architecture/adr/ADR-002-mvp-source-set.md) and [ADR-010](architecture/adr/ADR-010-source-connector-architecture.md): how licence flags drive behaviour.

## Terms used in the documents

- **R1-R9** are the research workstreams (R1 desk workflows and interfaces, R2 commercial products and adjacent
  applications, R3 open-source applications, R4 open-source libraries and MCP servers, R5 information sources and live
  collection tests, R6 data engineering, deduplication and clustering, R7 AI and agents, R8 multimedia, R9 legal and
  licensing). Findings are numbered `F-<letter>-<nn>` by topic letter.
- **Deliverables 01-16** are the numbered documents of the research round. Where a document cites "deliverable 12" or
  "12 section 6", the table below gives the file.
- **Supplement 01 / 02** are two requirement notes from the project owner (deployment flexibility; customer-owned
  content licensing). They are not published; the documents restate what they require.
- **Model A / Model B**: A means the provider acquires and distributes news content; B means the provider supplies
  software that processes content the customer licensed independently. The product is Model B.
- **O1-O4** are AI modes: O1 fully deterministic, O2 plus single LLM calls, O3 plus embeddings, O4 an external agent
  through MCP. The MVP is specified to be fully functional in O1.
- **Release A / A.1**: the built subset. **MVP-1**: the larger later target.

| Deliverable | File |
|---|---|

| 01 | [business/industry-and-business-process-report.md](business/industry-and-business-process-report.md) |
| 02 | [business/commercial-product-landscape.md](business/commercial-product-landscape.md) |
| 03 | [technology/open-source-technology-evaluation.md](technology/open-source-technology-evaluation.md) |
| 04 | [sources-and-licensing/information-source-and-api-registry.md](sources-and-licensing/information-source-and-api-registry.md) |
| 05 | [technology/computational-methods-report.md](technology/computational-methods-report.md) |
| 06 | [technology/ai-and-agent-integration-report.md](technology/ai-and-agent-integration-report.md) |
| 07 | [technology/multimedia-and-broadcast-report.md](technology/multimedia-and-broadcast-report.md) |
| 08 | [sources-and-licensing/legal-and-licensing-report.md](sources-and-licensing/legal-and-licensing-report.md) |
| 09 | [specification/requirements-traceability-matrix.md](specification/requirements-traceability-matrix.md) |
| 10 | [architecture/build-vs-reuse-matrix.md](architecture/build-vs-reuse-matrix.md) |
| 11 | [architecture/recommended-architecture.md](architecture/recommended-architecture.md) |
| 12 | [specification/mvp-specification.md](specification/mvp-specification.md) |
| 13 | [specification/implementation-backlog.md](specification/implementation-backlog.md) |
| 14 | [specification/testing-and-evaluation-plan.md](specification/testing-and-evaluation-plan.md) |
| 15 | [reviews/consolidated-research-synthesis.md](reviews/consolidated-research-synthesis.md) |
| 16 | not published (an internal implementation brief) |

## Index

Top level: [decision-log.md](decision-log.md) (process and architecture decisions) and [evidence-conventions.md](evidence-conventions.md).

### Business and desk practice (`business/`)

Who the users are, how a foreign-news desk works, what commercial products exist, and who would pay. Evidence comes from public job advertisements, trade press and vendor documentation.

| Document | Status |
|---|---|
| [Adjacent applications (workstream M, R2, 2026-11-25)](business/adjacent-applications.md) | Estimate |
| [Broadcaster licensing evidence (R2, supplement 02, 2026-11-25)](business/broadcaster-licensing-evidence.md) | Verified finding |
| [02 · Commercial product landscape (R2, round 1, 2026-11-25)](business/commercial-product-landscape.md) | Verified finding |
| [Desk-facing delivery practices (R1, verified 2026-11-25)](business/desk-practices.md) | Estimate |
| [Workflow decompositions (R1, verified 2026-11-25)](business/desk-workflows.md) | Estimate |
| [01 · Industry and business-process report (R1, 2026-11-25)](business/industry-and-business-process-report.md) | Estimate |

Registries and data tables: [commercial-products.csv](business/commercial-products.csv), [desk-responsibilities.csv](business/desk-responsibilities.csv).

### Sources and licensing (`sources-and-licensing/`)

Which feeds and APIs can be collected, under what terms, and what the Korean and international law and licences allow. Not legal advice.

| Document | Status |
|---|---|
| [Acquisition methods: feeds, conditional requests, change detection, browser automation (R5)](sources-and-licensing/acquisition-methods.md) | Verified finding |
| [04 · Information source and API registry (R5, Workstream D) — decision D2](sources-and-licensing/information-source-and-api-registry.md) | Verified finding |
| [08 · Legal, licensing and operational constraints (Workstream L, agent R9)](sources-and-licensing/legal-and-licensing-report.md) | Verified finding |
| [Korean statute extracts (R9, fetched 2026-11-25)](sources-and-licensing/statute-extracts.md) | Verified finding |

Registries and data tables: [oss-licenses.csv](sources-and-licensing/oss-licenses.csv), [source-registry.csv](sources-and-licensing/source-registry.csv).

### Technology (`technology/`)

Open-source applications and libraries that were evaluated or tested, computational methods, AI use and its threat model, multimedia, reliability and security.

| Document | Status |
|---|---|
| [06 · AI and agent integration report (R7, 2026-11-25)](technology/ai-and-agent-integration-report.md) | Experimental result |
| [AI threat model: news-monitoring system (R7, 2026-11-25)](technology/ai-threat-model.md) | Experimental result |
| [05 · Computational methods report (R6, Workstreams E + F, 2026-11-25)](technology/computational-methods-report.md) | Experimental result |
| [Data model, lifecycle and database choice (R6, Workstream E, 2026-11-25)](technology/data-model-and-lifecycle.md) | Design proposal (not built) |
| [MCP servers for news and monitoring data (R4, 2026-11-25)](technology/mcp-servers-evaluation.md) | Verified finding |
| [MCP tool design: news-monitoring system (R7, 2026-11-25)](technology/mcp-tool-design.md) | Design proposal (not built) |
| [07 — Multimedia and broadcast workflows (Workstream H, round 1, 2026-11-25)](technology/multimedia-and-broadcast-report.md) | Experimental result |
| [Multimedia and broadcast: standards, delivery and tooling (R8 source log, 2026-11-25)](technology/multimedia-standards-and-delivery.md) | Verified finding |
| [Open-source complete applications: evaluation (R3, workstream C, applications half)](technology/open-source-applications-evaluation.md) | Verified finding |
| [Components evaluation — libraries as dependencies (R4, 2026-11-25)](technology/open-source-components-evaluation.md) | Experimental result |
| [03 · Open-source technology evaluation (S1 synthesis of R3 and R4, 2026-11-25)](technology/open-source-technology-evaluation.md) | Experimental result |
| [Reliability and security review (Workstream J, S2, 2026-11-25)](technology/reliability-and-security.md) | Design proposal (not built) |

Registries and data tables: [applications-registry.csv](technology/applications-registry.csv), [components-registry.csv](technology/components-registry.csv).

### Experiments (`experiments/`)

Reports, methods and our own small analysis scripts. The raw corpus, captured feeds and model outputs over real articles are not published.

| Document | Status |
|---|---|
| [R7 API spend: ai_processing (2026-11-25)](experiments/ai-processing/cost.md) | Experimental result |
| [AI processing experiments: results (R7, 2026-11-25)](experiments/ai-processing/results.md) | Experimental result |
| [Cost — R4 component smoke (2026-11-25)](experiments/component-smoke/cost.md) | Experimental result |
| [Cost ledger — round 1 (2026-11-25)](experiments/cost-ledger.md) | Experimental result |
| [Experiment 1: URL canonicalisation, exact hashing, near-duplicate and syndication detection (R6, 2026-11-25)](experiments/deduplication/results.md) | Experimental result |
| [R6 API spend (2026-11-25)](experiments/event-clustering/cost.md) | Experimental result |
| [Corpus and Experiment 2: event clustering (R6, 2026-11-25)](experiments/event-clustering/results.md) | Experimental result |
| [Experiment 4: volume spike detection (R6, 2026-11-25)](experiments/event-clustering/spike-detection/results.md) | Experimental result |
| [Fts summary](experiments/korean-fts/fts-summary.md) | Experimental result |
| [Experiment 3: SQLite FTS5 for Korean and Chinese search (R6, 2026-11-25)](experiments/korean-fts/results.md) | Experimental result |
| [COST — R8 multimedia (2026-11-25)](experiments/multimedia/cost.md) | Experimental result |
| [Multimedia demo — RESULTS (R8, 2026-11-25)](experiments/multimedia/results.md) | Experimental result |
| [Trial — dgtlmoon/changedetection.io (R3, 2026-11-25)](experiments/repository-trials/changedetection-io.md) | Experimental result |
| [R3 API spend (2026-11-25)](experiments/repository-trials/cost.md) | Experimental result |
| [Trial — DIYgod/RSSHub as an npm library (R3, 2026-11-25)](experiments/repository-trials/rsshub.md) | Experimental result |
| [R5 API spend](experiments/source-collection/cost.md) | Experimental result |

Registries and data tables: [probe_summary.csv](experiments/source-collection/probe_summary.csv).

Scripts, prompts and small result files sit beside each report. Scripts that load credentials from a private workspace, generate
the backlog, or collect raw corpora are described in the reports but not published.

### Architecture (`architecture/`)

Build-versus-reuse matrix, the recommended architecture for the full MVP, and ten architecture decision records.

| Document | Status |
|---|---|
| [ADR-001 · Foundation strategy (D1): hybrid K-D, built as a library-assembled core (K-B) with optional out-of-process adapters](architecture/adr/ADR-001-foundation-strategy.md) | Historical decision |
| [ADR-002 · MVP source set (D2): keyless public feeds and official APIs, with registry licence flags that drive behaviour](architecture/adr/ADR-002-mvp-source-set.md) | Historical decision |
| [ADR-003 · MVP user and use case (D3): a foreign-news desk assistant, sold as software that processes content the customer already licenses (Model B)](architecture/adr/ADR-003-mvp-user-and-use-case.md) | Historical decision |
| [ADR-004 · Storage (D4): SQLite (WAL) + FTS5 with CJK bigram pre-tokenisation, behind a repository layer](architecture/adr/ADR-004-storage.md) | Historical decision |
| [ADR-005 · Deduplication and event clustering (D5)](architecture/adr/ADR-005-dedup-and-clustering.md) | Historical decision |
| [ADR-006 · Where AI is used, which provider, and how the system degrades without it (D6)](architecture/adr/ADR-006-ai-use-provider-degradation.md) | Historical decision |
| [ADR-007 · Video and broadcast (D7): deferred; the MVP is video-ready in schema and accepts text that rides with video](architecture/adr/ADR-007-video-and-broadcast.md) | Historical decision |
| [ADR-008 · Delivery surface (D8): editorial queue + flash notice + reviewed digest, with a read-only API and MCP server](architecture/adr/ADR-008-delivery-surface.md) | Historical decision |
| [ADR-009 · Deployment flexibility: what the single-tenant MVP decides now, and what it defers](architecture/adr/ADR-009-deployment-flexibility.md) | Historical decision |
| [ADR-010 · Source connector architecture: one ingestion contract for public feeds, customer-licensed wires, local files and newsroom systems](architecture/adr/ADR-010-source-connector-architecture.md) | Historical decision |
| [10 · Build vs. reuse matrix (S1, 2026-11-25)](architecture/build-vs-reuse-matrix.md) | Design proposal (not built) |
| [11 · Recommended system architecture (S1, 2026-11-25)](architecture/recommended-architecture.md) | Design proposal (not built) |

### Specification (`specification/`)

The full MVP specification, traceability, implementation backlog and test plan. Most of this is not built.

| Document | Status |
|---|---|
| [13 · Implementation backlog (S2, 2026-11-25)](specification/implementation-backlog.md) | Design proposal (not built) |
| [Interface specification: MVP surfaces and monitoring profiles (Workstream I output, S1, 2026-11-25)](specification/interface-spec.md) | Design proposal (not built) |
| [12 · MVP specification (S1, 2026-11-25)](specification/mvp-specification.md) | Design proposal (not built) |
| [09 · Requirements traceability matrix (S1, 2026-11-25)](specification/requirements-traceability-matrix.md) | Design proposal (not built) |
| [14 · Testing and evaluation plan (S2, 2026-11-25)](specification/testing-and-evaluation-plan.md) | Design proposal (not built) |

Registries and data tables: [backlog.csv](specification/backlog.csv), [test-catalogue.csv](specification/test-catalogue.csv), [traceability.csv](specification/traceability.csv).

### Reviews and synthesis (`reviews/`)

Independent reviews and the consolidated synthesis of the research round.

| Document | Status |
|---|---|
| [15 · Consolidated research synthesis (round 1, 2026-11-25)](reviews/consolidated-research-synthesis.md) | Historical decision |
| [REVIEW_V1 · Independent adversarial review of deliverables 03–14 (V1, 2026-11-25)](reviews/review-v1.md) | Historical decision |
| [Round 3 review: consolidation and simplification (2026-11-25)](reviews/round3-review.md) | Implemented (Release A + A.1) |

## What is not published

- Raw corpora and captured third-party news text (feeds, article bodies, HTML snapshots), model outputs over real
  articles, embeddings, and raw API responses.
- Saved copies of the public job advertisements the desk-practice evidence was drawn from. Documents cite the
  employer and portal; short duty phrases are kept where a finding depends on them.
- Internal planning files, session prompts, and scripts that read credentials from a private workspace.
- Generator scripts for the backlog and traceability matrix. Their outputs are published.

References in the documents to unpublished material are plain text, for example "private experiment data (not published)".

## Caveats

- These notes were written largely by AI research agents under the project owner's direction. First-person statements
  ("I fetched", "I did not inspect") refer to those agents.
- Every time-sensitive fact (prices, star counts, terms, limits) is dated; the default date is 2026-11-25. Re-check
  before relying on it.
- Legal material is research, not legal advice. Statute text came from the law.go.kr Open API; contract readings are
  marked INFERRED where they are.
- Experiment samples are small (tens to a few hundred articles). Gold labels for clustering were assisted by an LLM and
  only partly spot-checked.
