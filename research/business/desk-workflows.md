# Workflow decompositions (R1, verified 2026-11-25)

> **Status: Estimate.** Workflow decompositions from public job advertisements, vendor pages and articles; no insider account of a desk shift was found. Per-cell evidence tags apply.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Scope: the seven workflows named in the R1 brief. Row-level responsibilities with sources are in
[`business/desk-responsibilities.csv`](desk-responsibilities.csv) (IDs `R-nn` below). Every cell is tagged **[D]** DOCUMENTED (a posting, a
vendor page or an article says so), **[V]** VERIFIED (a primary source read in full for that claim), **[I]** INFERRED
(reasoned from named evidence) or **[U]** UNVERIFIED. Evidence base and its weaknesses are in
[`business/industry-and-business-process-report.md`](industry-and-business-process-report.md) §6. Read this first: most of the "how" below is thin. The postings
give duty lines, not procedures, and no insider account of a Korean 외신 monitor's shift was found.

Broadcaster and staffing-agency names from the job advertisements are withheld: 방송사 A and 방송사 B, and 인력 파견사 1-4, are used consistently across the business documents.

Sources used throughout (short names):
- **BA** = 방송사 A 국제부 job advertisement (public posting; image attachment read 2026-11-25).
- **BB** = 방송사 B 국제부 job advertisement (public posting via 인력 파견사 1, full text).
- **DHM** = 다하미 job advertisement.
- **SYN** = an earlier analysis of the public job advertisements; **M1** = job-listing search summaries (search-summary level). Neither is published.
- **HK** = 한국일보 국제부 야근 report, 2005, https://www.journalist.or.kr/m/m_article.html?no=10666 (a newspaper, not a TV monitor seat).
- **JN** = 기협 2018 국제부 report, https://www.journalist.or.kr/m/m_article.html?no=44301.
- **KBS** = Choi et al., 2022, 한국비블리아학회지 33(3), https://koreascience.kr/article/JAKO202228751849986.pdf (read in full as text; interviews July-Aug 2021).
- **BQD** = AISURFER help page, https://docs.channel.io/aisurfer/ko/articles/AI%EC%84%9C%ED%8D%BC-%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C-deb9fb0c
- **EC** = Economist.co.kr on AISURFER Brief, https://economist.co.kr/article/view/ecn202609140042
- **BR** = public-institution PR staffer blog, https://brunch.co.kr/@@aZC7/83 (one person's account).

---

## W1 · 외신 desk monitoring (방송사 A, 방송사 B; also 연합뉴스TV, MBC, 채널A)

| Attribute | Content | Tag / source |
|---|---|---|
| Seat | A 파견 contractor inside the broadcaster's 국제부. One seat works overnight on weekdays plus some weekend days; the other works evenings four days a week. | [D] BA, BB |
| Inputs | AP and other English-language foreign reports; APTN and Reuters footage on screen; footage and posts the desk asks for; English text and wire footage information. | [D] BA, BB (R-01, R-02, R-04) |
| Outputs | (1) An organised important-material entry registered in a PC system. (2) A notice (고지) to the desk when a feed item matters. (3) A summary of footage information and English text for the field reporter. (4) Translated or interpreted English where needed. | [D] BA (R-03), BB (R-02, R-05), 인력 파견사 3 (R-06) |
| Steps | Watch wires and feeds; decide an item is important; organise it (title, gist, link or clip); register it; tell the desk; on request, summarise or retrieve. Search for particular footage or posts. | Steps as a sequence: [I] from the duty lines; each duty line [D] |
| Decision points | "Is this important enough to report?" (the only real judgment); "does a reporter need this now?" | [I] |
| Frequency | Continuous during the shift. Item volume unknown for TV monitors. The only volume figure is ~700-800 wire items per night at a 2005 newspaper desk. | [D] HK (not a TV seat) |
| Time sensitivity | Minutes for breaking items. US announcements often land after 23:00 KST, and broadcasters cut regular programming for them. | [D] JN |
| Quality bar | Not stated for monitors. English is the real gate: "영어 가능자" (방송사 A), 영문 번역 and 시사 상식 preferred (방송사 B). | [D] BA, BB |
| Human-judgment points | Importance selection; reading tone of statements ("행간을 읽어야", a broadcast reporter on tweets); deciding what a reporter can use. | [D] JN for the quote; seat attribution [I] |
| Failure scenarios | A missed flash (the cost is a late or absent item on air); a wrong relay (four newspapers printed a staged-killing story from foreign reports); a mistranslation of a statement; the lone night person is unavailable. | Wrong relay [D] JN; others [I] |
| Software dependencies | A "PC" report system (name not given); the wire clients (AP and Reuters, product names not given in the postings); the broadcaster's MAM for footage. TV conversation channels (CNN on a wall TV) are second sources. | [D] BA for "PC등록"; HK for the CNN TV; the rest [I] |
| Automation opportunity | **Assist:** alerting on new wire items, deduplicating across wires, English→Korean draft summaries, a ranked "possibly important" queue, search across the day's items. **Not automatable in a text system:** watching APTN/Reuters footage (needs video, feed access). **Never full:** the decision to declare something important and to relay a statement. | [I] |

Open: how the monitor tells the desk in practice (a spoken call, a messenger, only the PC entry) is not stated anywhere found.
Searches run: "<방송사> 국제부 외신 모니터링 ... 어떻게 일하나", "<방송사> 국제부 외신 수신 APTN 로이터 ... 사보". Result: UNVERIFIED-absent.

---

## W2 · Wire monitoring and triage (AP, Reuters, AFP text and video)

| Attribute | Content | Tag / source |
|---|---|---|
| Inputs | Real-time agency copy under contract; an audible alert on new items; video wires; CNN or other channels on a wall screen. | [D] HK |
| Outputs | A few selected items passed on (<10 of ~700-800 per day reached the page); an organised overnight pile and a verbal/physical briefing for the morning shift. | [D] HK |
| Steps | Alert sounds; the item is checked on screen; kept or dropped; kept items translated or summarised; between editions the person reads for new stories; late at night the person translates English material and organises papers for the morning team. | [D] HK (2005 newspaper) |
| Decision points | Keep or drop each item; verify or hold when a foreign report is surprising. | [D] HK, JN |
| Frequency | Per item, all shift. | [D] HK |
| Time sensitivity | A wire "alert" is minutes. News from other time zones peaks in the small hours, which is why the shift exists. | [D] HK |
| Quality bar | Recall for must-carry items; precision matters because the page space is tiny. Provenance: the 2018 case shows a story passed on from foreign reports that proved false. | [D] HK, JN; quality bar as stated [I] |
| Human-judgment points | Everything after alerting: news sense, verification, priority. HK: the work "depends on judgment, news sense, and speed". | [D] HK |
| Failure scenarios | Missed flash; false relay; fatigue on night shifts; a single person alone from 02:00 (fewer than five in the newsroom). | [D] HK, JN |
| Software dependencies | Wire terminals/clients (AP Newsroom, Reuters Connect are the vendor products; their use by these desks is **not** documented). AP Newsroom lists breaking-news alerts with audio and topic-filtered homepages per a third-party mirror page. | [U] for the Korean desks; AP page [D] via mirror only (https://kompas.wasmer.app/https_www_ap_org/solutions/platforms/newsroom-platform; ap.org itself was not fetchable) |
| Automation opportunity | **Full:** collection, dedup, ordering, first-pass translation. **Assist:** importance scoring, summary. **None:** verification and the decision to relay. The 800:10 ratio is the main case for a ranked queue. | [I] |

Open: no TV-desk figure for items per night; AP/Reuters client-desk workflow documentation was not found (UNVERIFIED-absent after two searches: "AP Newsroom Reuters Connect newsroom wire desk alerts priority ...", "AP Newsroom features alerts video ingest ...").

---

## W3 · Foreign footage ingest and archive

| Attribute | Content | Tag / source |
|---|---|---|
| Inputs | Foreign footage received from agencies (APTN, Reuters, AFP at KBS); footage reporters request (other agencies, 국무부 브리핑 녹취). | [D] BB; [V] KBS for AP/AFP clips |
| Outputs | Classified, ingested clips with metadata, available for editors and reporters; periodically cleaned archive. | [D] BA, BB |
| Steps | Classify; ingest into the newsroom MAM; enter metadata (title, date/time, agency, content, names); store; tidy unneeded clips. At KBS the 원본영상 is registered right after reception, then reporters search it; after about two years it moves to a separate company archive and much metadata is lost. | [D] BA, BB; KBS details [V] |
| Decision points | Which category; whether to keep a clip; what to write in the title. KBS: reporters sometimes demand their own titles and ignore ingest conventions. | [V] KBS |
| Frequency | Per item or batch, all shift. | [I] |
| Time sensitivity | Medium: footage must be findable when the reporter needs it. | [I] |
| Quality bar | Consistent searchable metadata. KBS finding: manual entry depends on the person's style; dates entered in 6 formats and times in 3; AP/AFP clips often entered month-day-year; many clips lack reporter or location. KBS's rule sheet is 3 A4 pages. | [V] KBS |
| Human-judgment points | Content description and what to keep; no formal reporter review of ingest metadata exists at KBS. | [V] KBS |
| Failure scenarios | Footage cannot be found; wrong date; metadata lost on archive transfer. | [V] KBS |
| Software dependencies | KBS chain: 보도정보시스템 (reporters write, 데스킹, search) → 뉴스MAM (ingest, metadata, 외신수신본 managed with other resources) → NLE editors → 전자큐시트 → 송출제어. 방송사 A and 방송사 B systems are not named. MBN uses a "차세대 보도정보시스템 (NRCS)" built by CJ Olive Networks (search snippet only). | KBS [V]; MBN [U] (snippet: https://cjnews.cj.net/) |
| Automation opportunity | **Assist:** metadata normalisation (date/time/agency), duplicate detection of repeated feeds, cloud ASR/captions for searchable text, a controlled-vocabulary check at entry. **Blocked in round 1:** actual ingest needs MAM integration, wire access and video handling (R8, D7). | [I] |

---

## W4 · Feed-fault reporting

| Attribute | Content | Tag / source |
|---|---|---|
| Inputs | A received agency feed or clip that has a problem. | [D] BB |
| Outputs | A notice to the agency and to 기술국 (engineering); confirmation the fix was done. | [D] BB ("외신사, 기술국에 통보, 사후 처리 확인") |
| Steps | Notice the problem; tell the agency and engineering; check afterwards. | [D] BB |
| Decision points | Is it a source fault (agency) or a local one (engineering)? Who to call. | [I] |
| Frequency, time sensitivity | Event-driven; likely high during a live feed. | [I] |
| Quality bar, judgment | Not stated. Judgment is low (route the fault). | [I] |
| Failure scenarios | Fault noticed late; wrong party notified; no follow-up. | [I] |
| Software dependencies | Contact channels unknown. Reuters is migrating live news feeds from satellite to IP with TVU Networks (announced 2026-03-25; search-result mention only, page not read), which may change who owns fault detection. A 2016 archived UN guide lists Reuters TV support and APTN contact addresses, dated and not fault procedures. | [U] https://www.sportsvideo.org/2026/03/25/reuters-and-tvu-networks-begin-satellite-to-ip-migration-for-live-news-distribution/ |
| Automation opportunity | **Assist:** automated feed-health detection and a pre-filled fault note (time, feed, symptom). Needs video/stream access, so it is a D7 deferral. | [I] |

Searches run: "APTN Reuters news video feed fault reporting customer contact ..." Result: no published procedure (UNVERIFIED-absent).

---

## W5 · Client press clipping (비큐에이아이 AISURFER, 다하미 스크랩마스터, 조간/석간)

| Attribute | Content | Tag / source |
|---|---|---|
| Inputs | The press: about 3,000 outlets monitored by AISURFER; 스크랩마스터+ licenses about 300 print titles and 2,000 online outlets (다하미 is the official distributor of 한국언론진흥재단 뉴스저작권 사업단 "뉴스코리아"). Client keywords per account. | 3,000 outlets: [D] an analysis of public job advertisements and a Wanted search snippet (company self-description, not opened). 스크랩마스터+ figures: [D] https://apps.apple.com/kr/app/id1487909960 (read) |
| Outputs | A bundled file of selected articles; per-outlet counts of press-release pickup; monthly/quarterly issue-analysis report where contracted; reports published as PDF or table of contents from the AISURFER admin screen. | [D] BR, BQD |
| Steps | Set keywords and outlets; collect; group same articles (only for 20-2,000 hits per vendor help); select and scrap; (for the morning edition) a person works from about 04:00 for about 3 hours; evaluate; publish report; client staff review and upload to internal system. | [D] DHM, BQD, BR |
| Decision points | Is the article about the client? Is it positive, negative or neutral (평가)? Is it urgent? | [I] ("평가" meaning); [D] BR for crisis flagging |
| Frequency | Morning (조간) and evening (석간) daily: 다하미 Mon-Fri from 04:00 (~3h), Sat from 05:00 (~1h); 석간 Mon-Fri from 12:40 (~45min). | [D] DHM |
| Time sensitivity | Fixed cut-offs. The client wants the file "early in the morning"; negative coverage is wanted early for crisis response. Exact delivery times are not given beyond the work start times. | [D] DHM, BR |
| Quality bar | Completeness of client mentions, correct tone, no duplicates. No published accuracy standard. | [I] |
| Human-judgment points | Tone/priority rating; whether coverage is a crisis; analysis commentary; client relationship. | [D] BQ posting duties (SYN §3); BR |
| Failure scenarios | Missing a negative article; late file; wrong client's article included; copyright problems from uncontrolled redistribution. | [I]; copyright framing [D] (한국언론진흥재단 신탁 관리 per MCST search results, not read) |
| Software dependencies | The vendor's own platform (AISURFER, 스크랩마스터); email/PDF; client's internal system. | [D] |
| Automation opportunity | Largely **full** for collection, dedup, keyword match, first summary and spike alerts: the vendors already ship these (AI 요약, AI 기사 검색, 위기 알림, 동일기사 묶기). **Assist** for tone, analysis. **None** for client handling. The humans in the postings (BQ AIR팀, 다하미 home slots) still exist, so automation is not complete. | [D] BQD for features; [I] |

---

## W6 · Corporate / PR media intelligence

| Attribute | Content | Tag / source |
|---|---|---|
| Inputs | Organisation, brand, competitor and industry coverage in news (SNS planned). | [D] EC |
| Outputs | A scheduled briefing newsletter; urgent email alerts; delivery-result view; statistics where the plan allows (a search-result summary of AISURFER Brief also names Telegram as a channel; the pages read did not). | [D] EC; Telegram [U] |
| Steps | Group by department/brand/project; set keywords, outlets, managers, recipients; the system selects articles and **generates a draft on the user's schedule**; staff review and edit; send. Urgent issues have separate conditions and recipients. | [D] EC |
| Decision points | Edit or drop the draft; whether an issue is urgent enough to alert. | [D] EC |
| Frequency | Regular briefing on a user-set schedule; alerts event-driven; monitoring 24 hours. | [D] EC |
| Time sensitivity | Morning briefing for the day; urgent alerts minutes. | [D] EC (time of morning briefing not stated) |
| Quality bar, failure scenarios | Not stated; missed negative story or noisy alerts are the obvious failures. | [I] |
| Software dependencies | AISURFER Brief (opens October 2026, so it is a new product); email delivery. | [D] EC |
| Automation opportunity | **Full** for monitoring and draft; **assist** for the briefing text. The vendor's own design keeps a human review step. | [D] EC; [I] |

---

## W7 · Industry intelligence

| Attribute | Content | Tag / source |
|---|---|---|
| What was found | Only a named audience: strategy and management departments tracking industry and client trends use the same monitoring product. No workflow, cadence or output format was found. | [D] EC |
| Inputs, outputs, steps | Not established. A plausible shape is the W6 pipeline with wider keyword sets and longer-period summaries. | [I] |
| Automation opportunity | Same pipeline as W6 with trend/clustering over time (assist). | [I] |
| Limit | No dedicated source for this workflow was found in the time-box. Reported as a gap, not as a negative. | UNVERIFIED-absent |

---

## Reference: BBC Monitoring (international analogue)

| Attribute | Content | Tag / source |
|---|---|---|
| What it is | A BBC division that monitors and reports on mass media worldwide as open-source intelligence: radio, TV, press, agencies, online from about 150 countries, in up to 100 languages; ten overseas bureaus; London base; customers include the UK government and commercial clients. | [D] https://en.wikipedia.org/wiki/BBC_Monitoring (secondary; fetched 2026-11-25) |
| How the work is organised | Multilingual journalists navigate the sources, spot trends and verify material; automation covers social and online sources first; broadcast is harder because speech-to-text on names is "extremely difficult". The director of innovation says tools bolted on without rethinking the workflow waste their benefit. | [D] https://www.twingly.com/we-can-no-longer-successfully-do-our-job-without-the-help-of-automation-and-artificial-intelligence/ (interview with BBC Monitoring's Judy King, read 2026-11-25; interview date not stated) |
| Historic pipeline | Transcripts translated; experts selected key content; summarised and curated into daily reports with commentary. | [U] McMaster library snippet, page not opened |
| Customer-specific work | Monitors scan channels beyond their usual output for specific customers. | [U] UK Parliament oral-evidence snippet, page not opened |
| Why it matters | It is the clearest public statement that the **human selects and verifies, the machine widens coverage**, and that broadcast footage is the hard part. It matches the shape of W1/W5. | [I] |

Not obtained: BBC Monitoring's own site (fetch refused), the IWM "Listening to the World" research pages (HTTP 403), the Springer chapter (login redirect), UK Parliament evidence pages (HTTP 403). No current BBC Monitoring workflow description was read at source.

Adjacent, not decomposed: **송출·편성 모니터링** (class C): watching playout channels. It is a different job (channel quality, schedules, 3-shift) and outside round 1.
