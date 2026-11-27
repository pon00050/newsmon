# Desk-facing delivery practices (R1, verified 2026-11-25)

> **Status: Estimate.** Desk practices from public job advertisements, trade-press articles and vendor pages. Per-row evidence tags apply.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Informs **D8** (delivery surface) and **D3**. Tags as in [`evidence-conventions.md`](../evidence-conventions.md). Short source names are defined in
[`business/desk-workflows.md`](desk-workflows.md). **Headline limit:** no source found describes how a Korean 외신 monitor
actually tells the desk (voice, messenger, system). The only hard fact is that the posting says reports are registered in a
"PC". Everything about messengers is UNVERIFIED-absent. The clipping side is better documented, because vendors publish
what they deliver.

## 1. How a monitor notifies a desk today

| Mechanism | Evidence | Tag |
|---|---|---|
| Registering an organised important item in a system ("중요 자료 정리 및 보고(PC등록 작업)") | 방송사 A job advertisement, duty 3 | DOCUMENTED |
| Telling the desk about important foreign footage ("외신 화면 모니터 및 고지") | 방송사 B posting duty 1 | DOCUMENTED |
| Writing a summary for the reporter producing the package ("취재기자 제작 지원") | 방송사 B posting duty 2 | DOCUMENTED |
| Telling the wire agency and the engineering department when a feed breaks ("외신사, 기술국에 통보") | 방송사 B posting duty 4 | DOCUMENTED |
| Audible alert for new wire copy; the night person checks each on a monitor | 2005 newspaper desk, HK https://www.journalist.or.kr/m/m_article.html?no=10666 | DOCUMENTED (newspaper, old) |
| Briefing the next shift on overnight developments with organised materials left on the desk | HK | DOCUMENTED (newspaper, old) |
| Phone calls to correspondents to clarify copy | HK | DOCUMENTED (newspaper, old) |
| KakaoTalk / Slack / email digests between monitor and desk | searches: "<방송사> 국제부 외신 모니터링 ... 어떻게 일하나"; none found | UNVERIFIED-absent |

What the posting wording tells us: the report is a **record in a system** (so it persists, can be searched by the next shift
and by reporters) and the notice (고지) is a separate act. A delivery surface for a desk assistant therefore needs both a
**persistent queue entry** and an **immediate notification**. That is INFERRED from the two duty lines; the actual tools
are unknown.

## 2. What a "중요 자료 보고" contains

No template was found. The duty line gives its verbs: 정리 (organise) and 보고 (report) by PC registration. Fields below
are INFERRED from what a reporter would need and from KBS's ingest paper, not from a seen form.

| Likely field | Basis | Tag |
|---|---|---|
| Source (agency, URL or feed) and time received | KBS paper: agency and time are fields that ingest staff enter, and they are often entered inconsistently (6 date formats, 3 time formats) https://koreascience.kr/article/JAKO202228751849986.pdf | VERIFIED for KBS ingest; the report form itself INFERRED |
| Title or gist in Korean | Duty 2 of 방송사 B (summaries to support reporters) | INFERRED |
| Why it matters / what a reporter may use | Duty "중요 자료" implies selection | INFERRED |
| Link or clip reference | Duty "중요영상 및 게시글 검색" implies items are clips and posts | INFERRED |
| Provenance and verification status | The 2018 staged-killing story that four papers carried from foreign reports (JN, https://www.journalist.or.kr/m/m_article.html?no=44301) shows the cost of an unsourced relay | DOCUMENTED for the case; field INFERRED |

## 3. What a clipping report looks like

| Item | Finding | Tag / source |
|---|---|---|
| Format | The vendor sends the selected articles bundled as **one file** by email early in the morning; the client PR staffer reviews and uploads it to an internal system. Some contracts add a monthly or quarterly issue-analysis report. | DOCUMENTED, one PR staffer's account https://brunch.co.kr/@@aZC7/83 |
| Content | Positive articles, negative articles, articles that used press releases, broadcast news, plus per-outlet counts of press-release pickup. | DOCUMENTED, same blog |
| Vendor products | AISURFER: keyword/company/policy monitoring, AI article search with source articles, AI summary, scrap folder, report built from scrapped articles with a table of contents (published as table of contents or with PDF), crisis alerts when keywords spike. | DOCUMENTED https://docs.channel.io/aisurfer/ko/articles/AI%EC%84%9C%ED%8D%BC-%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C-deb9fb0c |
| AISURFER Brief | Monitors 24 hours; **generates a briefing draft on the user's schedule; staff review and edit it before it goes out as a newsletter**; urgent issues go as email alerts under separate conditions and recipients; delivery results (success, failure, bounce) are viewable. Announced at K-ICT WEEK in BUSAN 2026 (September 9-11), opening October 2026. | DOCUMENTED (press article about the announcement) https://economist.co.kr/article/view/ecn202609140042 |
| Telegram as a channel | A search-result summary of the same product named email and Telegram; the pages I read named email only. | UNVERIFIED |
| 스크랩마스터+ | The app has auto-search with alerts at check intervals of 10, 30, 60 (default), 120 or 180 minutes, a scrap that can be shared with web and PC versions, and AI analysis for online articles (v2.1.19). Users asked for next-day date ranges to see early-edition papers. | DOCUMENTED https://apps.apple.com/kr/app/id1487909960 (read; App Store page and reviews) |
| Report layout (cover, order, tone labels) | No sample report was found. | UNVERIFIED-absent (searches: "기업 홍보팀 언론 모니터링 조간 스크랩 보고서 형식 ...") |

## 4. Cut-off times and cadence

| Audience | Cut-off or cadence | Tag / source |
|---|---|---|
| 조간 clipping (다하미 home worker) | Work starts Mon-Fri **04:00** and lasts about 3 hours; Saturday starts 05:00 for about 1 hour. | DOCUMENTED (a public job advertisement) |
| 석간 clipping | Starts Mon-Fri **12:40**, about 45 minutes. | DOCUMENTED same file |
| Client delivery time of the morning file | "아침 일찍" only; the exact hour is not given. A working-end time of ~07:00 (04:00 + 3h) is INFERRED. | DOCUMENTED (early morning) / INFERRED (07:00) |
| Early-edition papers | A 스크랩마스터 reviewer wanted next-day dates to capture early editions, which implies the evening cut-off is tied to the papers' release times. | UNVERIFIED (one review, App Store page) |
| 외신 desk | Continuous across the shift; peak around US time announcements, often after 23:00 KST. | DOCUMENTED JN |
| Shift handoff | Newspaper night editor stayed past press time at about 04:00 to organise materials for the morning team. | DOCUMENTED HK (newspaper, 2005) |

## 5. Latency and quality tolerance by audience

| Audience | Latency tolerated | Quality emphasis | Tag |
|---|---|---|---|
| TV 국제부 reporters and the news desk | Minutes for flashes; before air for summaries. | Not mis-stating foreign statements; speed. | INFERRED from posting duties plus JN (broadcasters cut programming for breaking news; misreading tweets happens) |
| Client PR departments (clipping) | Fixed morning/midday deliveries; early negative-coverage warning matters more than the exact minute. | Completeness of mentions; correct tone; no duplicates. | DOCUMENTED (BR purposes) / INFERRED (completeness) |
| Strategy departments (industry intelligence) | Hours to days; scheduled briefing. | Relevance and trend, not exhaustiveness. | INFERRED from EC (named audience only) |
| Ingest/archive users (editors) | Findable when needed; retrospective. | Consistent metadata. | VERIFIED KBS (the problem), INFERRED (tolerance) |

## 6. Implications for D8 (stated as options, not decisions)

1. **A persistent queue is required** by the "PC등록" report and the need to hand over between shifts (INFERRED).
2. **A scheduled digest is required by the clipping profile**; vendors build it as a draft that a person reviews (DOCUMENTED, EC).
3. **Alerts are needed for two cases only**: a desk flash (minutes) and a client crisis spike. Vendors alert by email (DOCUMENTED, EC). Whether a Korean desk would accept messenger alerts was not established.
4. **API/MCP surfaces** have no evidence from desk practice; they are an engineering convenience, not a user need found here (INFERRED).
5. The strongest design lesson is the vendor's own: **draft-for-review beats auto-send** for the briefing, and a wrong relay is costly (JN case), so every item should carry its source link and timestamp.

## 7. Not established

- Any template or sample of 중요 자료 보고 or of a clipping report.
- The messenger/phone behaviour of monitors; the names of the PC/NRCS and wire clients at Korean broadcasters' 국제부 desks.
- Whether delivery by KakaoTalk, Telegram or Slack is accepted by desks. Searching for this is a round-2 offer (cost: a few searches; chance it changes D8: low, because queue + email digest covers both profiles regardless).
