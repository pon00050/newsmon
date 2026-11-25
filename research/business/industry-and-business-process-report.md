# 01 · Industry and business-process report (R1, 2026-11-25)

> **Status: Estimate.** Deliverable 01. Built on public job advertisements and articles; the evidence base and its weaknesses are stated in section 6.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Question.** What do the people in Korean news-monitoring seats actually do, step by step, and what does that say about the
MVP's first user and use case (D3) and its delivery surface (D8)?

**Basis.** The 50 public job advertisements already scanned (not republished), the duty text of every class A
(외신 monitoring) and class B (media-monitoring service) posting, plus public sources fetched or searched on 2026-11-25. This
report is self-contained; the details are in [`business/desk-workflows.md`](desk-workflows.md),
[`business/desk-practices.md`](desk-practices.md) and [`business/desk-responsibilities.csv`](desk-responsibilities.csv) (49 rows).
Tags: DOCUMENTED / VERIFIED / INFERRED / UNVERIFIED as in [`evidence-conventions.md`](../evidence-conventions.md).

## 1. Answer in one paragraph

The 외신 desk seat and the client-clipping seat are **the same pipeline with different profiles**: collect from many sources,
drop duplicates, pick the few items that matter, summarise or translate them, and deliver them. They differ in what triggers
delivery (an event for the desk, a clock for the clipping client), in what the user sees (a queue plus an immediate notice for
the desk; a bundled morning/evening file for the client), and in what "good" means (the desk wants **precision** on "important";
the client wants **recall** on "mentions us"). A large part of the real 외신 seat (about half of the duty lines at TV조선, most at YTN) is **video and broadcast-system work** (watching
APTN/Reuters footage, ingest, archive, feed faults) that a text-based round-1 MVP cannot do. The clipping market is **already
served** by Korean vendors with AI summary, search, report and alerts, so it is a poor place to differentiate, and its source
material is copyright-managed. A **desk-assistant profile on English text** is the more defensible first target, with the
clipping digest as a second profile on the same pipeline. That is a recommendation to the orchestrator, conditional on D2 and
the legal findings (§5), not a decision.

## 2. Findings

### F-A-01 · The 외신 seat is half video, and the video half is not reachable in round 1
- Finding: TV조선's duty list is four lines: monitor AP and other English-language reports; classify and ingest foreign footage;
  organise and report important material (PC registration); search important footage and posts. YTN's is four lines: monitor
  APTN/Reuters footage and notify; summarise footage information and English text for reporters; save footage to the
  archive; notify the agency and engineering when a received feed has a problem. By duty count, 3 of 4 YTN lines clearly involve footage, archive or feed health; at
  TV조선 one line (classify and ingest footage) does, and a second (search important footage and posts) partly does.
- Evidence: DOCUMENTED, the TV조선 and YTN job advertisements (verified 2026-11-25).
- Limits: duty lines carry no time split; "half" is a count of duties, not of hours.
- Implication: a text-only system covers monitoring AP text, 중요 자료 정리/보고, search, summary/translation, but not
  footage monitoring, ingest, archive or fault detection. Feeds D3 and D7.

### F-A-02 · The desk's report is a system entry, and the notice is a separate act
- Finding: "중요 자료 정리 및 보고(PC등록 작업)" (TV조선) and "외신 화면 모니터 및 고지" (YTN). The two verbs imply a **persistent record** plus a
  **live notification**. Nothing found says how the notice is delivered (spoken, messenger or system).
- Evidence: DOCUMENTED (same postings). Delivery channel: UNVERIFIED-absent (searches in DESK_PRACTICES §1).
- Implication for D8: the surface needs a searchable queue (shift handoff, reporters) and a notification path. Do not
  design around a messenger the evidence does not name.

### F-A-03 · Triage ratio is about 80:1 on a wire desk, and a wrong relay is expensive
- Finding: a newspaper international night desk handled about 700-800 wire items a day and fewer than 10 reached the page. A 2018
  report records four papers printing a staged-killing story from foreign reports. TV-seat volumes are unknown.
- Evidence: DOCUMENTED, https://www.journalist.or.kr/m/m_article.html?no=10666 (2005, newspaper) and https://www.journalist.or.kr/m/m_article.html?no=44301 (2018).
- Limits: both are newspaper desks, one is 20 years old. Order of magnitude only.
- Implication for D5/D6/D8: dedup plus a ranked queue is the main value; every item must carry source link, timestamp and a
  provenance note. AI should rank and summarise, never relay unverified claims as fact.

### F-A-04 · The clipping workflow is schedule-driven and small-team, but the software is mature
- Finding: 다하미's home clipping slots are 조간 Mon-Fri from 04:00 (~3h) and 석간 from 12:40 (~45min). A client PR staffer
  reports receiving one bundled file by email early each morning, reviewing it and uploading it internally; some contracts add a
  monthly or quarterly analysis. AISURFER offers monitoring of ~3,000 outlets, AI search and summary, scrap, report and crisis
  alerts. 스크랩마스터+ licenses about 300 print titles and 2,000 online outlets through 뉴스코리아.
- Evidence: DOCUMENTED, a public job advertisement; https://brunch.co.kr/@@aZC7/83 (one staffer); https://docs.channel.io/aisurfer/ko/articles/AI%EC%84%9C%ED%8D%BC-%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C-deb9fb0c; https://apps.apple.com/kr/app/id1487909960.
- Implication for D3: a new clipping MVP would reproduce what is on sale, and would need licensed Korean news to match it
  (D2/L, R9). The market's remaining human work is tone judgment, analysis and client handling.

### F-A-05 · The vendors keep a human between the draft and the client
- Finding: AISURFER Brief generates a briefing draft on the user's schedule; staff review and edit before sending; urgent
  issues go as email alerts under separate rules; delivery results are viewable. Announced September 2026, opening October 2026.
- Evidence: DOCUMENTED https://economist.co.kr/article/view/ecn202609140042.
- Implication for D6/D8: "AI drafts, person approves" is the incumbent pattern. Design for it from the start; it also
  gives a way to degrade without AI (a keyword-ranked draft).

### F-A-06 · Foreign-footage metadata is manual and inconsistent in the one Korean broadcaster studied
- Finding: at KBS, ingest staff type title, date, time and content by hand; dates appear in 6 formats and times in 3; AP/AFP
  clips are often entered month-day-year; many clips lack reporter or place; there is no reporter review of ingest metadata;
  metadata is lost on transfer to the company archive after about two years. System chain: 보도정보시스템 → 뉴스MAM → NLE →
  전자큐시트 → 송출제어; 외신수신본 are kept in the 뉴스MAM.
- Evidence: VERIFIED, https://koreascience.kr/article/JAKO202228751849986.pdf (read as text, 2026-11-25; interviews July-August 2021).
- Limits: KBS is not one of the five 24-hour channels; the paper does not cover wire text.
- Implication for D7: video ingest is a metadata-normalisation problem that automation could help, but it needs MAM integration. Defer.

### F-A-07 · BBC Monitoring's public framing supports "machine widens, human selects and verifies"
- Finding: journalists navigate sources, spot trends and verify; automation is applied first to social and online sources;
  broadcast is harder because speech-to-text on names is "extremely difficult"; tools must fit the whole workflow.
- Evidence: DOCUMENTED, https://www.twingly.com/we-can-no-longer-successfully-do-our-job-without-the-help-of-automation-and-artificial-intelligence/ (interview with Judy King, undated) and https://en.wikipedia.org/wiki/BBC_Monitoring.
- Limits: no current BBC Monitoring workflow page was reachable (site fetch refused; IWM, Springer and Parliament pages 403/login).
- Implication for D6/D7: matches the approach to start with text and defer broadcast.

### F-A-08 · The 외신 market remains two live seats; job-market facts are not re-checked here
- Per an analysis of public job advertisements: TV조선 and YTN, always through staffing agencies; hours are night/evening/weekend. Not repeated here.
  This matters only as context: the "user" of a desk assistant is a contractor monitor or the reporter beside them, **not a
  buyer with a budget**. Evidence: DOCUMENTED, a public job advertisement. Who would pay is a B-workstream (R2) question.

## 3. Workflow summary

| Workflow | Trigger | Output | Mostly text? | Human judgment | Automation fit | Evidence strength |
|---|---|---|---|---|---|---|
| W1 desk monitoring | event | registered important item, notice, summary | partly | high (what matters) | assist | duty lines DOCUMENTED; procedure thin |
| W2 wire triage | per item | few kept items, handoff note | yes | high | full for collect/dedup/rank, assist for importance | newspaper-desk sources only |
| W3 footage ingest and archive | per item | metadata + clip in MAM | no | low-medium | assist (normalise metadata) | one KBS paper VERIFIED |
| W4 feed-fault reporting | event | notice to agency and engineering | no | low | assist, needs stream access | one posting |
| W5 client clipping | clock (조간/석간) | bundled file, report | yes | tone, analysis | mostly full (vendors ship it) | postings and vendor pages |
| W6 corporate/PR intelligence | clock + event | newsletter draft, alerts | yes | review before send | full draft, human approve | one press article |
| W7 industry intelligence | clock | trend brief | yes | high | assist | audience named only |

## 4. Implications for the decisions

**D3 (MVP user and use case).** Recommend the orchestrator weigh: (a) *desk assistant on English text* targets the part of the
seat that automation can reach and gives a measurable output (a ranked, deduplicated, summarised queue); (b) *clipping* has a
clear schedule and a ready buyer type but is crowded and licence-bound. Both are served by one pipeline, so choose by what is
testable in round 2: English public sources for (a), licensed Korean feeds for (b). What would change this: R5 showing no
usable English wire-like source, or R9 showing Korean RSS/headline use is clean.

**D7 (video).** Duty counts say video is central to the real seat, but the work is ingest, MAM and feed health, which needs
integration the round cannot test. Defer; keep the data model able to hold a clip reference.

**D8 (delivery surface).** A persistent queue (handoff, search) plus a scheduled digest drafted for review plus email alerts for
two cases (desk flash, client crisis). Messenger and API/MCP have no desk-practice evidence found; treat them as options.

## 5. Dependencies on other workstreams

- D2/L: what English and Korean text may be collected continuously decides whether the desk profile has real inputs. AP and
  Reuters are not accessible in this project.
- B (R2): who pays and how much; this report found users, not buyers.
- H (R8): whether cloud ASR on State Department briefings or footage is viable is the only automatable video piece.

## 6. Evidence quality, limits and what was not done

- **Thin on purpose:** no insider account of a Korean 외신 monitor shift, no sample 중요 자료 보고, no clipping report layout, no AP
  Newsroom or Reuters Connect client documentation read at source (ap.org was not fetchable; the feature list came from a mirror page).
  These are UNVERIFIED-absent. Searches run are listed in [`business/desk-workflows.md`](desk-workflows.md) and [`business/desk-practices.md`](desk-practices.md). No known-answer or nonsense
  control query was run on the search tool, so a "not found" supports "not easily found", not "does not exist".
- The class B duty text for BQ AI (AIR팀) and for 유니에스 comes from an analysis of public job advertisements, which read images with vision on 2026-11-25; I
  did not re-read those images because their hosts' `robots.txt` disallows fetching. I read the TV조선 and YTN
  images from a host that allows it. The TV조선 weekday-variant image and the second YTN image were not opened; they are copies of the same seat.
- 크릭앤리버's saved advertisement has no duty text; an analysis of public job advertisements is the source for "same minus search".
- Sources used with caution: a single PR staffer's blog; a Wikipedia page; one 2005 newspaper report; one 2018 report; vendor
  and press pages (DOCUMENTED at best).
- Not done: market sizing, outreach to any desk or vendor, price comparison (R2), any build or experiment.

## 7. Registry and file index

- [`business/desk-responsibilities.csv`](desk-responsibilities.csv): 49 rows (R-01..R-49): 42 DOCUMENTED, 2 VERIFIED, 5 UNVERIFIED; 15 `full`, 30 `assist`, 4 `none`. Coverage: all duty lines of the TV조선, YTN, 다하미, BQ AI and 더이음 postings are present.
- [`business/desk-workflows.md`](desk-workflows.md); [`business/desk-practices.md`](desk-practices.md).
