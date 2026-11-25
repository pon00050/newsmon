# 02 · Commercial product landscape (R2, round 1, 2026-11-25)

> **Status: Verified finding.** Deliverable 02. Vendor documentation read on 2026-11-25; items marked UNVERIFIED remain unchecked.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Decisions informed:** D3 (MVP user and use case), D1 (does a buyable service make building pointless), D2 (licensed feeds).
**Method and limits:** desk research, 31 web searches and fetches (23 searches, 8 fetches, of which 3 were blocked), search-summary level. Capped workstream: no pricing detail, no trials, no
vendor contact. Several primary vendor pages could not be fetched (developer.ap.org, developers.reutersconnect.com, wikidocs, which the
fetch tool refused or returned 403 for), so AP and Reuters facts rest on third-party mirrors and catalogs. Every row is in
[`business/commercial-products.csv`](commercial-products.csv) (27 rows, tag and URL per row, all verified 2026-11-25). Market size is not estimated.

## 1 · Bottom line

1. **No buyable product covers the desk-assistant seat described in an analysis of public job advertisements** (watch wires, classify and ingest foreign footage,
   summarise and translate for reporters, archive briefing transcripts, report feed faults). The products found split into four groups
   that each cover a slice. INFERRED from the product rows; the absence of a fitting product is UNVERIFIED-absent (see §6).
2. **The wire itself is the unavoidable paid dependency.** AP and Reuters content comes only through a licensed account (AP Newsroom /
   AP Media API / Media Agent; Reuters Connect and its API). The broadcasters already hold those licences. A tool that sits on top of a
   broadcaster's own licence is a different product from one that must obtain its own wire feed. DOCUMENTED (rows P01–P04).
3. **The client-clipping use case is the better-served market, and it is gated by licensing, not by software.** In Korea the working
   products (AISURFER, 스크랩마스터) sell *licence tiers for press content* (전자스크랩, 내부 라이선스, 통합 라이선스) along with the software.
   A new entrant would first need a licensing route, which R9 owns. DOCUMENTED (P18, P19); implication INFERRED.
4. **Leaning for D3 (not a decision):** the foreign-news desk assistant is the use case the commercial market serves least, and the one
   where a lightweight system adds something. The reasoning is INFERRED and has two weak points: the unmet need is seen only through
   job ads, not through desk interviews (R1), and absence of a product is not proven.
5. **Leaning for D1:** a buyable API does not make building pointless for the *desk assistant*. It does make it pointless to build a
   *general text clipping engine* from scratch for domestic press, where AISURFER already sells event clustering, cited-answer search,
   briefings and an API (API availability itself is only partially documented).

## 2 · What the named products actually are

| Group | Products | What they sell | Row ids |
|---|---|---|---|
| Wire licensors | AP (Newsroom, Media API, Media Agent), Reuters Connect | Licensed content and the means to pull it | P01–P04 |
| Licensed news databases and APIs | Factiva, Nexis / Newsdesk / Data+ | Rights-cleared archive search, alerts, APIs; marketed for RAG | P08, P09 |
| Monitoring SaaS | Meltwater, Cision, Talkwalker, NewsWhip, Dataminr | Saved searches, alerts, dashboards, sentiment, spike detection | P06, P07, P10–P12 |
| Aggregation and open data | Feedly, GDELT, Event Registry, Google Alerts | Cheap collection, clustering, RSS | P13–P16 |
| Human service | BBC Monitoring | Human-selected, human-translated digests | P17 |
| Korean | AISURFER, 스크랩마스터, BIGKinds, gig and custom clipping | Domestic press clipping and analysis under news-copyright licences | P18–P22 |
| Broadcast production | Dalet, Avid, Ross, Vizrt/Mosart, Korean MAM vendors | Ingest, MAM, rundowns, ASR tagging | P23–P26 |

### F-B-01 · "AP Media Agent" exists under that name, and is a feed-download tool, not an AI agent
- Question: the pasted claim about an "AP Media Agent": real, and what is it?
- Finding: AP's developer page describes the "AP Media Agent and Configuration Dashboard" as the tool to "download a continuous feed of
  content from up to the last 72 hours" and to "set up and manage your ingestion agents and content download preferences". The older AP
  Media API Portal "has been integrated with AP Newsroom and is now called AP Media Agent Configuration Dashboard". The "agent" is an
  ingestion agent for a licensed feed. A separate third-party catalog lists a `GET /media/v/content/feed` endpoint, not shown to be the same mechanism.
- Evidence: first pass DOCUMENTED via a mirror; superseded by section 8, where the AP pages were read at source (VERIFIED). Mirror URL:
  https://kompas.wasmer.app/https_developer_ap_org/ap-media-api (verified 2026-11-25). Second-source support: jentic.com catalog states
  access is by `apikey` and gated by AP's content licensing.
- Limits (first pass; section 8 resolves formats, auth and the Agent mechanism, but not rate-limit numbers): formats, auth, rate limits, and whether it is push or poll were UNVERIFIED. An npm package `ap-mcp-server`
  appeared in results (socket.dev); not examined, and may be unrelated to AP.
- Implication: using AP Media Agent requires an AP licence; it is outside round 1 (non-goal: no AP access). Design the ingest layer so
  a licensed feed can be added later as one more source.
- Open: does the broadcaster's licence permit a third-party tool to run the agent? (R9.)

### F-B-02 · Dataminr, NewsWhip and Meltwater show alerting beyond keyword match
- Finding: Dataminr alerts on detected events with location and ticker metadata, and a reviewer reports too many irrelevant alerts;
  NewsWhip alerts on predicted engagement and limits to currently popular content; Meltwater advertises spike detection and
  sentiment-shift alerts. All three are vendor claims.
- Evidence: DOCUMENTED — https://www.g2.com/products/dataminr/features ; https://www.newswhip.com/newswhip-spike/ ; https://www.meltwater.com/en/capabilities/media-intelligence (verified 2026-11-25).
- Implication: an alert-threshold design should include a velocity or spike rule and an explicit false-alert measurement from the
  start (D8). INFERRED.

### F-B-03 · The Korean clipping market is licensed in tiers; AISURFER's design is the closest commercial analogue
- Finding: AISURFER sells 전자스크랩 (search, scrap, print), 내부 라이선스 (internal sharing within the contract), 통합 라이선스 (plus
  external distribution and website publishing). 스크랩마스터's App Store text says it legally covers about 300 print and 2,000 online
  titles and names 다하미커뮤니케이션즈 as a distributor in the 한국언론진흥재단 뉴스저작권 programme. AISURFER Brief adds group rules (per
  department, brand, project: keywords, media, managers, recipients), a morning briefing, urgent alerts, a draft-then-staff-review step,
  and send/bounce status.
- Evidence: DOCUMENTED — docs.channel.io/aisurfer pages and economist.co.kr/article/view/ecn202609140042 ; apps.apple.com/kr/app/id1487909960 (verified 2026-11-25).
- Limits: the two AISURFER sources disagree on delivery channels (Telegram appears in one summary, not in the article) and on
  sentiment; API availability is reported for higher plans in one source only; prices not published.
- Implication: the client-clipping path needs a news-copyright licence before it has a product (D2, D3). The human review step before a
  digest goes out matches the BQ AI job ad's 언론 보고서 분석 duty and is a pattern to copy.

## 3 · Established industry practices (across the rows)

- **Saved query profile as the unit of work.** Meltwater saved searches, AISURFER keyword+media sets, Factiva/Nexis Boolean plus filters,
  Google Alerts queries. Boolean is still the expert interface, with an AI query-builder layered on top (Meltwater). DOCUMENTED.
- **Two delivery rhythms.** A scheduled digest (morning, and per the seat descriptions evening) and an immediate alert for urgent
  terms. AISURFER Brief, Google Alerts (hourly/daily/weekly), Meltwater. DOCUMENTED.
- **Licensed-content walls.** Content access is by contract with usage tiers (view, internal share, external distribution; AP and Reuters
  licence scope; Reuters standard offer forbids downloading or copying, per a 2021 FAQ). The product sells content rights as much as software.
- **Event clustering as a first-class object.** Event Registry returns clustered events; AISURFER's AI certification covers issue clustering; GDELT codes events. DOCUMENTED.
- **Cited-answer AI.** AISURFER's article search returns an answer with the source articles shown; Factiva and Nexis market rights-cleared
  retrieval for RAG. DOCUMENTED (vendor claims).
- **Human translation and selection remain a premium tier.** BBC Monitoring states sources are translated by editorial teams, not
  machine translation. DOCUMENTED (library page citing BBCM).
- **Agent-plus-preferences for wire ingest.** AP's Media Agent: an ingestion agent configured with download preferences and a bounded look-back window.
- **Broadcast MAM adds ASR tags to ingest.** Dalet Media Cortex gives speech-to-text transcripts and auto-tags; the sources are 2016–2023 trade press. DOCUMENTED, dated.

## 4 · Reusable architectural patterns

| Pattern | Seen in | Use for |
|---|---|---|
| Query profile = keywords + media set + owners + recipients | AISURFER Brief | One config object for digests and alerts across clients or desks |
| Digest draft, then human release | AISURFER Brief | Quality gate where AI summaries are wrong at a cost (D6) |
| Spike rule over a rolling baseline | Meltwater, Dataminr, AISURFER 위기 알림 (surge) | Alert threshold that is not a raw keyword hit |
| Rolling-window pull with per-account preferences | AP Media Agent (72 h) | Bounded ingest and cheap replay |
| Delivery receipt tracking (sent, failed, bounced) | AISURFER Brief | Proof the digest went out; ties to the feed-fault duty |
| Scrap folder → report with table of contents | AISURFER | Reporter-facing output from a queue |
| Licence tier as a field on every item (view, internal, external) | AISURFER, 스크랩마스터 | Enforce the licence wall in the data model (R9, D2) |
| Cluster object linking articles | Event Registry, GDELT | Dedup and event grouping (D5) |
| RSS as the lowest-cost alert channel | Google Alerts, Feedly | Free sources in the MVP (D2) |

## 5 · Unmet needs and where a lightweight alternative fits (INFERRED)

Evidence for the need comes from the job-ad synthesis (an analysis of public job advertisements), not from product reviews. Product text did not show these functions:

1. **Desk triage of foreign wire plus footage for a broadcast reporter.** Monitoring SaaS (P06–P12) is built around social and press
   coverage for PR clients; wire licensors (P01–P04) deliver content but not triage; MAM (P23–P26) is heavy and broadcaster-owned.
2. **Feed-fault reporting.** The seat duty "tell the wire service or engineering when an incoming feed breaks" has no product row. The
   nearest is delivery-receipt tracking and ingest-agent status. UNVERIFIED-absent.
3. **English summarisation for reporters with source cited and a human check.** AISURFER does cited answers for Korean press; nothing
   found does it for English wires. UNVERIFIED-absent.
4. **Archive of recurring official briefings** (State Department transcript style). Factiva/Nexis are archives of publishers, not of
   government briefings. UNVERIFIED-absent.
5. **Low-cost clipping for tiny clients.** Evidence of demand at gig scale (P21), but licensing for Korean press content is unresolved.

A lightweight system fits where the licence is already held by the user (broadcaster's wire account, public RSS, open government
sources) and the work is triage, summary and fault reporting rather than selling press content.

## 6 · Unavoidable costs and dependencies that constrain architecture

| Dependency | Constraint | Status |
|---|---|---|
| AP and Reuters wires | Only via contract; cannot be collected or tested in this project (non-goal) | DOCUMENTED |
| Korean news copyright (한국언론진흥재단 뉴스저작권) | Clipping and redistribution of Korean press runs through licensed tiers | DOCUMENTED (P18, P19); legal reading is R9's |
| LLM cost per item | Cited summarisation and cluster labels cost per call; free sources keep the baseline cheap | INFERRED |
| Vendor API terms | AP, Reuters, Factiva, Nexis APIs gated by contract; Feedly API on Enterprise tier only per third-party text | DOCUMENTED, partial |
| Open data reliability | GDELT Doc API reliability reports are anecdotal; BIGKinds terms not found | UNVERIFIED |
| Broadcaster systems access | No access to MAM or wire accounts in round 1 | Non-goal |

**Architecture consequences:** (a) every item carries a source, licence tier and permitted-use flag; (b) ingest is pluggable so a
licensed feed is one adapter; (c) the system must be useful with free sources only; (d) AI is optional per step, since licensed wires
may bar sending text to a third-party model (R9 to confirm).

## 7 · What was not established

- AP Media API/Agent: read at source in the supplement pass (section 8). Reuters Connect API primary documentation: still blocked, UNVERIFIED.
- Cision, NewsWhip and Talkwalker feature detail, prices of everything, current Factiva API documentation.
- Vizrt/Mosart and Avid MediaCentral: no useful hit (UNVERIFIED-absent). Korean MAM vendor list is incomplete; one 2014 vendor document only.
- "Other Korean media-monitoring products": one targeted query for several named competitors found none of them; only AISURFER, 크몽 gigs,
  Dalpha and a 시전원 headline surfaced. This is not a control-validated absence.
- BIGKinds terms of use and API conditions.
- Instrument controls (known-answer and nonsense queries) were not run for any absence claim; every absence here is UNVERIFIED-absent.

## 8 · Supplement 02: customer-owned content licensing (Model A and Model B)

Added 2026-11-25 on the project owner's supplement. Evidence rows are in [`business/broadcaster-licensing-evidence.md`](broadcaster-licensing-evidence.md) (cited here
as E-A for AP documentation, E-B for contracts, E-C for job descriptions). Legal analysis of contract restrictions is R9's; this section is commercial.

### 8.1 What the evidence established, and what it did not

- **AP Media Agent is a customer-run ingestion tool for content the customer is already entitled to.** It is a Java application the customer
  downloads and registers with the customer's own API key. It writes files and metadata to folders the customer's CMS watches. Formats:
  NewsML-G2 XML or JSON item metadata, NITF text (story, caption, script, shotlist, timecoded transcript), and media renditions; folders per
  entitlement or per version, `ItemID--Version--ContentID` naming, a 24-hour duplicate filter, optional auto-delete. Look-back is 72 hours.
  VERIFIED (E-A1, A4–A12).
- **The Media API authenticates with the customer's key** in the `x-api-key` header over HTTPS, and exposes feed, search, single-item, On-Demand
  and RSS endpoints, an entitlements endpoint (`/account/plans`) and a per-account quota endpoint (`/account/quotas`). VERIFIED (E-A14–A16). Rate-limit
  numbers are account-specific and were not found. The API holds 30 days of content; the Agent 72 hours (E-A2, A3).
- **Consequence for the commercial question:** the integration surface an outside software vendor needs already exists and is designed for the
  customer's own systems: a watched folder of standard-format files, or the customer's own key. A vendor that only reads that folder never touches
  AP's servers. Whether the contract permits third-party processing is a contract question (R9), not answered by documentation.
- **No contract record was found.** The Arirang ₩888,030,000 / 2026–2028 APTN figure was supplied to the project as a claim and was not located (six searches, no
  controls; E-B). The 나라장터 and ALIO search pages, which are the right places, were not worked through. So the claim that broadcasters buy
  wire video under disclosed contracts is **supported by job descriptions (E-C) but not yet by a contract record in this project.**
- **Job descriptions show the seats work on wire video**: YTN's text names APTN and "토이터" (likely 로이터) monitoring, summarising, archiving and
  reporting feed faults to the wire and engineering (E-C). That implies broadcaster-held feeds. It does not show who operates the Agent.

### 8.2 The two models, evaluated separately

| | **Model A: provider acquires, processes and distributes content** | **Model B: software processes content the customer already licenses** |
|---|---|---|
| What is sold | Content plus a monitoring service (AISURFER and 스크랩마스터 today; Meltwater, Factiva, Nexis abroad) | Software that runs on the customer's own wire, MAM or folder feeds |
| Buyers | Companies, agencies and public bodies without wire access, who want press coverage | Broadcasters and newsrooms that already hold AP, APTN, Reuters or 연합뉴스 contracts (seats in E-C) |
| Who holds the content licence | The vendor, with redistribution tiers passed to customers (view, internal share, external publication) | The customer; the vendor needs none for the content, only the right to process it on the customer's behalf (R9) |
| Cost structure | Licence fees to publishers scale with customers; content is the cost of goods | No content cost; costs are software, integration, and any external AI calls |
| Integration points | Web app, email, API | Watched folder (AP Media Agent output), customer API key, NRCS, MAM, CMS |
| Entry barrier | A news-copyright licensing route in Korea, plus coverage breadth | Access to a customer's systems, trust, and per-site integration work |
| Incumbents | Strong: AISURFER (about 3,000 outlets, briefings, clustering, API on some plans), 스크랩마스터 (about 300 print and 2,000 online titles) | None found for foreign-wire desk triage; MAM vendors (Dalet, Avid, Ross) sit close but are heavy (UNVERIFIED-absent) |
| Fits the desk seat? | Poorly: it clips domestic press for PR, not foreign wire video and English text | Directly: the seat is triage over wire material the broadcaster already receives |
| Evidence status | DOCUMENTED (rows P18, P19) | AP mechanics VERIFIED; buyer existence INFERRED from job descriptions; contract record not found |

**What they already run (Model B buyers).** From the evidence: AP Media Agent or an equivalent ingest (AP's own pages say it feeds a CMS watching
a folder); an NRCS (AP lists an "ENPS/Storytelling API" beside the Media API, so an ENPS-style newsroom system is a documented AP integration
target, E-A18); and a MAM with an archive (the YTN seat saves incoming video to an archive; Dalet and Avid are the usual vendors, UNVERIFIED for
the Korean channels). Which Korean channels run which product was not established.

**Integration points for a Model B tool, in order of independence from the customer's vendors:**
1. A watched local folder (AP Agent output, or any wire drop): standard formats, no API credentials, works for the MVP with sample files and mock data.
2. Customer-supplied API credentials to the Media API (`x-api-key`) or Reuters Connect, read-only, run on the customer's side.
3. NRCS and MAM connectors: per-vendor, per-site; defer.
4. Output back to the customer's CMS or newsroom system by the customer's own mechanism.

**How AISURFER and 스크랩마스터 fit each model.**
- Model A: they are the model. They hold the press licences and resell tiered rights. Their licence tiers show that Korean domestic press is licensed
  by use. A Model B vendor must stay out of that business: it should not collect, store or re-serve press content it was not given by the customer.
- Model B: neither product processes a customer's wire folder, so they are adjacent, not competitors, for the desk seat. They are competitors if the
  Model B product drifts toward domestic clipping. The BQ AI broadcast-archive project (P27) shows the same vendor already sells to broadcasters,
  so it could extend into Model B. INFERRED; no evidence it plans to.
- They could also be complementary: a Model B tool for foreign wires and a Model A service for domestic press feed one desk. INFERRED.

### 8.3 What this changes in sections 1–6 (INFERRED)

- Section 1 point 2 (licensed wire is the unavoidable paid dependency) holds for Model A and does **not** bind Model B: under B the licence is the
  customer's and the project needs none to demonstrate the software. This matches the supplement's instruction that paid wire access is not an MVP prerequisite.
- The D3 lean toward the desk assistant gets structural support: it is the use case where Model B applies. The weak points stand: need seen
  through job ads (R1), no contract record, unknown who operates Agent and MAM at each channel.
- Cost to confirm: asking one broadcaster desk (or R1's interview route) which ingest, NRCS and MAM they run, and whether their wire contract
  allows third-party software and cloud AI to process files. That one answer would settle more than further desk research.

## Appendix · Searches and fetches run (2026-11-25)

Searches: AP Media Agent; AP Media API docs; Reuters Connect API; AISURFER 비큐AI; 스크랩마스터 다하미; "AP Media Agent" configuration dashboard;
AP Newsroom/APTN features; Superdesk ingest; Dataminr; Meltwater/Cision; Factiva/Nexis (two queries); Feedly; Event Registry;
BIGKinds; Korean monitoring competitors; NewsWhip/Talkwalker; GDELT; BBC Monitoring; Google Alerts; Dalet/Avid; broadcast wire ingest
(two queries); Korean MAM. Fetches: developer.ap.org (blocked), docs.channel.io AISURFER features and pricing pages, wikidocs (403),
economist.co.kr AISURFER Brief, developers.reutersconnect.com (blocked), Ross Streamline AP Media feeds help page, mt.co.kr BQ AI article.

Supplement pass (about 30 more): AP pages fetched at source with `curl` after WebFetch refused (Overview, Welcome, Getting Started, Content file types, Content save options, System requirements, Quick Reference FAQs, developer.ap.org/ap-media-api landing, api.ap.org docs landing, Swagger spec); 6 contract-record searches (see [`business/broadcaster-licensing-evidence.md`](broadcaster-licensing-evidence.md)); local reads of the job-description files.
