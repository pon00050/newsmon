# 15 · Consolidated research synthesis (round 1, 2026-11-25)

> **Status: Historical decision.** Deliverable 15: the synthesis written at the end of the research round. Superseded where it disagrees with the decision log.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

> **Status (2026-11-25, Round 3):** HISTORICAL. The research conclusion as of round 1. What was then built is narrower: see `../README.md` and [`decision-log.md`](../decision-log.md) P-011, P-013, P-015.

**Question.** What is the fastest, most reliable and technically defensible way to assemble a working news-monitoring
and intelligence system from existing technology and AI-assisted development?

**Answer in one paragraph.** Build a small, single-tenant Python application from well-maintained libraries. No
existing application is a usable foundation. The application must work **fully deterministically** (rules, MinHash,
TF-IDF, SQLite FTS5) and treat hosted-LLM calls as optional enrichment, switched per capability and per source. Aim the
first product at the **foreign-news desk**, not at press clipping. Sell it as **software that processes content the
customer already licenses** (Model B: AP/APTN, Reuters, 연합뉴스 files delivered by tools such as AP Media Agent),
plus free public feeds. Demonstrate it on synthetic wire files and public feeds, so no paid subscription is needed. The
specification, the 64-task backlog and the test plan are ready. Implementation then started from a private implementation brief; Release A + A.1 followed (see the decision log).

Evidence tags follow [`evidence-conventions.md`](../evidence-conventions.md). Every claim below points to the deliverable that carries its evidence.

---

## 1. What has been established

| # | Finding | Tag | Where |
|---|---|---|---|
| 1 | The 외신 seat has two halves. One is text: wire monitoring, summaries for reporters, 중요 자료 보고 as a system entry ("PC등록"), search. The other is video: footage classification, ingest, archive, feed-fault reporting. About half of the posted duty lines are video, ingest or feed-fault work (방송사 B: 3 of 4) | DOCUMENTED | 01 F-A-01 |
| 2 | Newspaper desks see ~700–800 wire items a day; under 10 reach the page. The value is a deduplicated, ranked queue with sources, not more text | DOCUMENTED | 01 |
| 3 | Clipping (Model A) is a mature, licence-bound market. AISURFER and 스크랩마스터 already sell AI search, clustering and briefings, under licence tiers tied to 한국언론진흥재단 news copyright. No product was found that serves the foreign-wire desk seat itself | DOCUMENTED / UNVERIFIED-absent | 02 §1, §8 |
| 4 | AP Media Agent is a Java ingest tool, not an AI agent. The customer registers it with their own API key, and it writes NewsML-G2 / JSON / NITF files and media renditions into a folder a CMS watches. The AP Media API uses an `x-api-key` header over HTTPS | VERIFIED (AP docs) | 02 §8, [`business/broadcaster-licensing-evidence.md`](../business/broadcaster-licensing-evidence.md) |
| 5 | AP and Reuters content cannot be collected without the customer's contract. Reuters robots.txt forbids it, AP returns 403 and robots disallows `/*.rss` | TESTED / VERIFIED | 04, 03 |
| 6 | Public feeds work technically: 36 of 36 live feeds (EN 18, KO 11, ZH 7) returned 200, and 18 honoured conditional GET. But most working KO/ZH feeds state "personal, non-commercial" terms, korea.kr RSS was discontinued, and state.gov returned 403 | TESTED / DOCUMENTED | 04 |
| 7 | Korean law has **no TDM exception**. The live 저작권법 was checked with a known-answer control. Unlicensed commercial clipping is not defensible (§30; AP v. Meltwater). The licence-free floor is headline + link + source + own-words summary | VERIFIED | 08 §0–§5 |
| 8 | Under Model B, a vendor stays a processor rather than a distributor when it holds no rights in the content, keeps each customer's content isolated, and the customer chooses the sources and starts ingestion with its own credentials. **Whether this works for a given customer depends on that customer's contract.** No AP, Reuters or 연합뉴스 customer terms are public. Published terms elsewhere (e.g. APA, Austria) are examples only and say nothing about Korean contracts | INFERRED (statutes VERIFIED) | 08 §13 |
| 9 | Licence assessment of the open-source candidates: n8n's Sustainable Use licence and SSPL rule out commercial use. AGPL (RSSHub, Firecrawl, FreshRSS, superdesk) is acceptable only unmodified or out-of-process. Two leads have no licence, and one lead returns 404 | VERIFIED | 08, `oss_licenses.csv` |
| 10 | **No open-source application is adoptable.** Taranis AI is closest (~6 of 9 capabilities after adjusting for fit), but it needs a 7-service Docker stack, is built for security-incident (CSIRT) teams and uses local models. Readers (miniflux, FreshRSS) lack clustering, triage and AI. AIHOT (MIT) and OpenNews (no licence) are design references | VERIFIED (code) / TESTED (2 trials) | 03 |
| 11 | **Libraries cover every text stage without local models:** feedparser, httpx, trafilatura, htmldate, extruct, courlan, datasketch, rapidfuzz, SQLite FTS5, Datasette. Smoke-tested on live BBC and Yonhap feeds. Yonhap ignores conditional GET, so dedup must rely on content hashes | TESTED | 03, `component_smoke/` |
| 12 | SQLite FTS5 handles Korean and Chinese **only with the right tokenisation**. Trigram + LIKE or character-bigram pre-splitting gives recall 1.00. The default tokenizer gives 0.68 (KO) and 0.09 (ZH). Trigram MATCH silently misses 2-character queries (북한, 中国) | TESTED | 05 |
| 13 | Dedup: MinHash-LSH, with t=0.9 for copies and t=0.5 for rewrites, beats SimHash, which found 45% of rewrite pairs. Count sources by registrable domain (75 hosts collapsed to 31 domains). Treat Yonhap "(종합)" updates as revisions | TESTED | 05 |
| 14 | Event grouping: embeddings with incremental clustering scored pair F1 **0.78**, against **0.37** for TF-IDF (HDBSCAN 0.41). Cross-lingual linking is weak with either. The gold set is LLM-assisted, with about half of it hand-checked | TESTED (with stated limits) | 05 |
| 15 | Hosted LLM enrichment is cheap and reliable at the format level. Haiku costs ≈ $1–5/day at 1–3k items/day. 142 schema-constrained calls had 0 parse failures, though some outputs broke the schema's meaning. Single relevance scores are noisy (35–62 for one item), so use coarse bands. Articles never hijacked a tool-less call, but injected text inflated scores even while flagged, so flagged items must go to human review | TESTED | 06 |
| 16 | Video: the ffmpeg black, freeze and silence detectors caught 3 of 3 injected faults and stayed quiet on 12 of 12 clean checks. Groq Whisper transcribed 60 s of English correctly at ≈ $0.04 per audio hour. Use ninjs field names and IPTC Media Topics (CC BY 4.0). Licensed video access is the blocker, not the technology | TESTED / VERIFIED | 07 |

## 2. What was independently verified, and how

- **Executed in this project (TESTED):** the source probes (88-row registry), the component smoke tests, two repository
  trials (changedetection.io, RSSHub), four algorithm experiments (dedup, clustering, Korean/Chinese FTS, spike
  detection), three AI experiments (extraction and summary, triage, prompt injection) and the multimedia demo. Scripts,
  inputs and outputs are under private experiment data (not published). Total API spend was about **$1.32**: AI $1.10, clustering labels
  $0.21, ASR $0.002 ([`experiments/cost-ledger.md`](../experiments/cost-ledger.md)).
- **Checked against primary sources (VERIFIED):** Korean statute text through the live law.go.kr API; repository licences
  and activity through the GitHub API and source reading; AP's official developer documentation; the IPTC standards.
- **Instrument controls:** known-answer and nonsense controls were run for the source probes, the FTS search and the
  detectors. A control caught a real bug in Python's `urllib.robotparser`.
- **Independent review:** [`reviews/review-v1.md`](review-v1.md) (§7 below records its outcome).

## 3. What already exists, and what we reuse

The full matrix is deliverable 10. In short:
- **Adopt** for collection and storage: feedparser, httpx, trafilatura, htmldate, courlan, datasketch, SQLite FTS5.
- **Adopt** for the application layer: FastAPI/htmx for the UI and API; the MCP Python SDK for read-only tools.
- **Integrate (optional, out-of-process, off by default):** RSSHub and changedetection.io as source adapters.
- **Reference:** AIHOT and OpenNews (pipeline design), superdesk-core (wire-format parsers, AGPL, so read but not
  linked), Taranis AI.
- **Standards:** ninjs and NewsML-G2 field naming, IPTC Media Topics.
- **Implement:** the connector contract, the licence gate and DisplayPolicy, normalisation, revision tracking, event
  grouping, the rules engine, alerts, digests, UI, audit, and the deployment seams.

## 4. What remains to be developed

The 64-task backlog (deliverable 13) runs in 15 waves.
- **Critical path to O1 acceptance:** about 60 hours of coding sessions, a rough estimate. No AI task sits on it.
- **Specified tests:** 243, of which 179 run in O1 mode, 33 against a mocked AI client, and 4 live tests that run only on
  request.
- **Coverage of the seat:** 11 of the 49 atomic desk responsibilities are fully served, 13 partially and 25 not. The video
  half of the seat and the clipping duties are out (deliverable 09).

## 5. What remains uncertain

| Uncertainty | Why it matters | How to resolve |
|---|---|---|
| What each pilot customer's AP, Reuters or 연합뉴스 contract allows (service providers, storage, hosted vs customer-hosted AI) | Decides whether Model B works for that customer, its flag values, and customer-hosted vs managed deployment | Read the real contract with the customer and their counsel (OQ-1) |
| Whether internal organisational use fits the "personal / non-commercial" terms of several feeds; 12 publishers' terms unread | Decides which public sources run in `internal` context | Korean counsel; round-2 terms reading (OQ-2, OQ-3) |
| Route for sending names in news text to a US-hosted LLM (PIPA §28-8) | Default AI routing for Korean customers | Counsel; entity masking or a customer-hosted endpoint (OQ-5) |
| Thresholds for relevance and clustering on real desk judgement | The current gold sets are LLM-assisted and tuned on the data they are scored on | A desk-labelled set from a working monitor (OQ-7) |
| Korean ASR quality, real NRCS/MAM landscape at each channel | Needed before any video or newsroom-integration phase | Round-2 tests and interviews (OQ-10) |
| The Arirang APTN contract (₩888,030,000, 2026–2028) | Market evidence for Model B buyers only; it does not change the design | User-provided; not located by R2 in six searches (OQ-11) |
| Whether a Korean AI rewrite of a short feed summary from a headline-only source counts as an "own-words summary" or as a translation | Decides whether O2 can show Korean summaries for public headline-only sources (FR-06(f) currently withholds them) | User + Korean counsel (OQ-12) |
| Whether `kiwipiepy` (ships a small statistical model) fits the no-local-inference policy | Optional Korean ranking improvement only | Project-owner decision (OQ-4) |

## 6. Recommended implementation strategy and the smallest meaningful MVP

- **Strategy (ADR-001):** hybrid K-D, built as a library-assembled Python core. It runs as one process with a scheduler
  and stores everything in SQLite (WAL) + FTS5, with bigram pre-tokenisation behind a repository layer.
  - It follows ports and adapters, with 12-factor config.
  - It is single-tenant, but `workspace_id` is present on owned tables from day one.
  - It runs on Windows or Linux without Docker.
- **Operating modes (ADR-006):**

  | Mode | What it adds |
  |---|---|
  | **O1** | Fully deterministic. This is the baseline, and it is acceptance-tested in its own right |
  | **O2** | Single tool-less, schema-constrained LLM calls for Korean summary, translation and extraction |
  | **O3** | Cloud embeddings for event grouping |
  | **O4** | An external agent querying through the read-only MCP tools |

  No runtime agents and no training.
- **MVP (deliverable 12):** a desk assistant for one 외신 monitor or editor.
  - **Inputs:** 27 public EN/KO/ZH sources, plus a watched inbox of wire files with two synthetic wire sources (one
    gated, one demo).
  - **Processing:** dedup, revisions, event grouping, and rule-based bands with explanations.
  - **Desk surfaces:** an editorial queue with verdicts (the "PC등록"), flash and spike alerts by email, feed-health
    incidents, KO/ZH/EN search, and template or AI-drafted digests that a person approves.
  - **Interfaces and operations:** a read-only API and MCP, an audit log, export, backup and restore.
  - **Licence handling:** customer-entered licence flags with attestation drive every display and AI decision.

## 7. Independent review outcome

An independent Opus reviewer that wrote none of the work audited deliverables 03–14 ([`reviews/review-v1.md`](review-v1.md)):

- **Evidence integrity:** 28 TESTED or VERIFIED claims were sampled, and **0 tags were overstated**. Injection-flag counts
  were recounted from raw outputs, and the AP pages were re-fetched.
- **No blocker defects.**
- **Two major defects, both fixed:**
  - V1-01: AI-derived quotes and near-translations could leak text from headline-only sources. Fixed by FR-06(f): AI
    fields obey `display`, with a 20-character substring test. Whether a short-summary rewrite counts as "own words" is
    left open as OQ-12.
  - V1-02: the AI digest draft was not licence-gated per item. Fixed by FR-22(e).
- **Seven minor defects, all fixed:** Yonhap seed flag, the DR-17 wording, audit-log fields, inbox scan timing, the
  corrected O1 clustering numbers (pair F1 0.34 at θ 0.2), a Model A delta in ADR-010, and release slicing.
- **S2's five known gaps were fixed in the source documents:** deliverables 10, 11 and 12.
- **Approved as written:** 02–07, 09 and ADR-001…009.

The backlog generator was re-run, and its coverage check passed with the three new tests. The MVP-1 release gate is
T-59's dependency closure (52 tasks). Process decision: P-010.

## 8. Next actions to begin implementation

1. (Historical.) Implementation was started from a private implementation brief. Its
   first deliverable was Wave 0 (T-01…T-08), ending in an O1 smoke test with no network and no AI.
2. In parallel (not code): start a pilot conversation with one licensed broadcaster to read its wire contract terms
   (OQ-1), and have Korean counsel answer OQ-3 and OQ-5.
3. Decide OQ-4 (kiwipiepy) when convenient. Nothing in the MVP depends on it.
4. Round-2 research offers (none blocks the build): terms for the 12 unread publishers; translate-then-embed for
   cross-lingual grouping; a Korean ASR test (≈ $0.01); a desk-labelled gold set; the NRCS/MAM landscape per channel.
