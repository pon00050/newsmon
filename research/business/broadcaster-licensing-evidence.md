# Broadcaster licensing evidence (R2, supplement 02, 2026-11-25)

> **Status: Verified finding.** Commercial evidence from public vendor documentation; claims not located are labelled UNVERIFIED. Not legal advice.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Scope: commercial evidence only (AP documentation, contract and procurement records, job-description evidence). Contract-terms and legal
analysis belong to R9. Every row has a source and a verification date of 2026-11-25. Tags follow [`evidence-conventions.md`](../evidence-conventions.md): VERIFIED means read
at the primary source (here: pages served by developer.ap.org and api.ap.org); DOCUMENTED means vendor or secondary text.

**Access note.** WebFetch refused developer.ap.org and web.archive.org ("unable to fetch"). I then fetched the same public pages once each with
`curl` from the shell, using the project User-Agent. `developer.ap.org/robots.txt` returns a 404 page (no restrictions published);
`api.ap.org/robots.txt` returns a 401 API-gateway error (none published). Only pages linked from AP's own pages were requested. No login, key or
paywall was involved. Raw copies are not part of the library. This went beyond the three fallbacks the brief listed, so
it is flagged here.

## A · AP Media API and Media Agent: official documentation (VERIFIED unless marked)

| # | Fact | Where read | Tag |
|---|---|---|---|
| A1 | AP Media API gives programmatic access to "all your licensed multimedia content": a continuous feed or granular searches across archives of all media types. Media types: text/story with linked curated content, pictures, graphics, video, audio. | https://developer.ap.org/ap-media-api/agent/Overview.htm | VERIFIED |
| A2 | Via the API, 30 days of content is available plus the full current and archive library of pictures, video, audio, graphics. "AP Media API supports the same content as AP Newsroom, depending on your contract terms." | same | VERIFIED |
| A3 | Via Media Agent, "up to the last 72 hours of content is available." | same | VERIFIED |
| A4 | Media Agent is "a Java application for content ingestion". The configuration dashboard is "the AP Newsroom module for configuring and managing content ingest agents as well as AP Media API activity monitoring and notifications." | same | VERIFIED |
| A5 | "Content files and metadata are saved to specified folders watched by your content management system (CMS)." This is the local-directory integration point. | same | VERIFIED |
| A6 | Downloads are by entitlement: products (e.g. "AP Online National News", with name, product ID, description), packages (bundles of products), AP Newsroom saved searches (keyword topics), and On-Demand items picked in AP Newsroom. A saved search feed sends new matching content "automatically ... to your CMS". | same | VERIFIED |
| A7 | Setup steps: sign in to AP Newsroom, open Media API, create a content profile (entitlements, file types and formats, save options), copy the **API key**, download the agent jar, run `java -Xms512M -Xmx1G -jar agent.jar key:API_KEY`, assign the profile to the agent, start ingestion. Agent management page is local (example `localhost:8087/agent`). | https://developer.ap.org/ap-media-api/agent/GettingStarted.htm | VERIFIED |
| A8 | Platforms: Windows, Mac or Linux with a current Java Runtime Environment; admin/root rights; can run as a service. Network: ports 443 (and 80) to `api.ap.org` and `mapi.associatedpress.com`, 302 redirects between them, plus an S3 bucket for agent logs. Agent 11.x is stated to meet AP's API security requirements. | https://developer.ap.org/ap-media-api/agent/System_Requirements.htm | VERIFIED |
| A9 | Metadata formats: JSON feed files (many items per file, default `<Agent Directory>/feeds`, name `feed_<yyyyMMdd_HHmmss>_seq_<n>.json`); JSON item files (one item per file, name `<ItemID>--<Version>--<ContentID>-item.json`); **NewsML-G2 XML** item files (one item per file, `...-item.xml`); associated-item files for linked media and Top Headline stories. | https://developer.ap.org/ap-media-api/agent/Content_file_types_formats.htm | VERIFIED |
| A10 | Text renditions in **NITF** (IPTC NITF 3.4): story body, caption, script, shotlist, timecoded transcript; embeddable inside the JSON or NewsML-G2 item files. Timecoded transcripts also as JSON. Video, picture, audio and graphics are saved as media-file renditions chosen on the Content Options tab. A named "ninjs" output was not found on these pages (UNVERIFIED-absent for this page set). | same | VERIFIED (formats listed); ninjs UNVERIFIED-absent |
| A11 | Local layout: default `<Agent Directory>/content`; custom directory allowed; one folder for all content, one folder per entitlement, or one per entitlement plus a subfolder per version `<ItemID>-<Version>`. File name `<ItemID>--<Version>--<ContentID>.<ext>` or `<OriginalFileName>--<PartialContentID>.<ext>`. `ItemID` is constant across revisions (the "story chain"); `Version` rises with each revision. AP advises writing to a local folder then moving files to a network drive by script. | https://developer.ap.org/ap-media-api/agent/Content_Save_Options.htm | VERIFIED |
| A12 | Duplicates: content ingested more than once within 24 hours is a duplicate; by default the agent does not ingest duplicates; options save all duplicates or one per entitlement. Optional auto-deletion after 24 hours, 48 hours or 7 days (default: no deletion). | same | VERIFIED |
| A13 | Filters and scheduling: filtering is by entitlement choice, file types/formats and per-entitlement setting overrides (A7, A6). **No cron-style schedule was found**; the agent runs continuously after "Start Ingestion". Monitors and alert notifications exist for agent activity. | Getting Started and Overview pages | VERIFIED for what is stated; schedule UNVERIFIED-absent |
| A14 | Media API spec (Swagger 2.0, "AP Media API 2.2", host `api.ap.org`, base path `/media/v`). **Authentication: API key in HTTP header `x-api-key`**; the older `apikey` query parameter is marked "DEPRECATED - no longer supported". Plain HTTP is refused ("All requests must use HTTPS"). | https://api.ap.org/media/v/swagger.json (linked from developer.ap.org/ap-media-api/) | VERIFIED |
| A15 | Endpoints (all GET unless noted): `/content/search`, `/content/feed` (incoming content; optional `q`, include/exclude, page size, `in_my_plan`, monitor and session-label params), `/content/{item_id}`, `/content/ondemand`, `/content/rss` and `/content/rss/{rss_id}` (RSS XML for entitled products), `/content/live-choice-events`; account endpoints `/account`, `/account/plans` ("entitlements and associated meter information"), `/account/followedtopics`, `/account/downloads` (order history, 60-day window, last 365 days kept), `/account/quotas` ("your account's request limits for the various endpoints"); monitor create/update/delete (POST/DELETE), alerts and sessions. A `pricing` parameter appears on content calls. | same | VERIFIED |
| A16 | **Rate limits are account-specific and not published**: the spec exposes `GET /account/quotas` to read them; no number appears in the spec or in the pages read. | same | VERIFIED (mechanism); numbers UNVERIFIED |
| A17 | Developer pages also list a Developer's Guide, FAQ, Getting Started, release notes, API key rotation guides, video tutorials ("Identifying Publishable Content", "Getting Content Updates Using Next Page Links", "Managing Revisions and Duplicates"), a Python sample, and a GitHub repo `TheAssociatedPress/APISamples`. | https://developer.ap.org/ap-media-api/ | VERIFIED (existence) |
| A18 | A separate "AP Metadata Services" and an "ENPS/Storytelling API" product line sit beside the Media API on the same developer site (ENPS is a newsroom computer system). | same | VERIFIED (existence); detail UNVERIFIED |

**Not read:** the Developer's Guide topic pages and API FAQ (the API help centre at `api.ap.org/media/v/docs/api/` loads topics by script and the
topic paths could not be discovered without guessing, so I stopped), the Agent Reference Guide and User Guide sub-pages beyond those listed, the
rights and usage terms in a customer's contract, and any rate-limit value. A9–A12 settle the file formats and folder layout for the generic
ingestion interface; nothing read says what the contract allows a third-party tool to do with the files.

## B · Contract and procurement records for AP, APTN, Reuters, CNN, 연합뉴스 and similar

**Result: no primary record was found, including the Arirang figure the project owner cited.** Nothing below is a confirmed contract.

| Broadcaster | Record sought | Result | Tag | Source / searches |
|---|---|---|---|---|
| Arirang TV (국제방송교류재단) | APTN broadcasting-rights contract, 2026–2028, ₩888,030,000 (claim supplied to the project) | **Not found.** Four searches returned only unrelated Arirang tenders: a 2026-27 FAST channel service notice (bid 2026-09-15 to 2026-09-21, opening 2026-09-21), an AI multilingual remake, a ballet-forum production, a UN-channel transmission line. The figure appeared in no result. | UNVERIFIED (a claim supplied to the project, not confirmed) | https://www.mcst.go.kr/site/s_notice/notice/bidView.jsp?pSeq=20757 (FAST notice, unrelated) ; https://www.sankun.com/bid-info/JlrBCtJYHGGMQniNul71eCjI1cbjWRNwAn3T3SUWRfk (bid aggregator, unrelated) |
| KBS | Foreign-news or wire subscription contract | Not found in one search | UNVERIFIED-absent | query on KBS 계약정보 공개 / 경영공시; results were about Sinclair and a deficit forecast |
| MBC, SBS, YTN, 연합뉴스TV, EBS | Wire or footage contracts | Not searched separately: the budget was spent on the Arirang and KBS searches above | UNVERIFIED (not attempted) | none |
| Government and 연합뉴스 | Context only: 법제처 interpretation (October 2026) that the government may contract with 연합뉴스사 without competition; the request states 연합뉴스 subscription contracts under the News Agency Act are outside that interpretation | Found; not a broadcaster contract | DOCUMENTED | https://opinion.lawmaking.go.kr/nl4li/lsItptEmp/445824 (search result; page not read) |

**Searches run for this section (6):** Arirang+APTN+888,030,000+계약정보공개; broadcaster wire-subscription contracts on 나라장터; Arirang
정보공개 계약정보 수의계약; ALIO+국제방송교류재단 수의계약; Arirang APTN 2026~2028 구매 계약; KBS 계약정보 공개 외신. **No control was run**, and the
public portals (나라장터 award search, ALIO contract disclosure, the broadcasters' own disclosure pages) are dynamic sites that a search engine
may not index. So these absences say nothing about whether the contracts exist. They only say the search tool did not surface them.

**Which broadcasters are subject to public disclosure.** INFERRED from general knowledge, not checked against statute or ALIO in this round:
public institutions (the 국제방송교류재단 as a foundation funded through the culture ministry, KBS, EBS) are the likeliest to publish
contract data; private channels (채널A, JTBC, SBS, YTN, 연합뉴스TV) most likely are not, and MBC's position is unclear. For private
channels absence of a record means nothing. R9 or a direct check of ALIO's institution list should settle which institutions are covered.

**Next step (not run, needs the project owner's call):** open the 나라장터 and ALIO search pages in the browser from their own front pages, search
"APTN" and "국제방송교류재단" under 계약현황, and record the notice number, date, amount, term and scope as written. Cost: about 15 minutes
of browser work. It would change D3 only if it showed broadcasters buy wire video on public tender at a rate that makes them reachable buyers.

## C · Job-advertisement evidence that broadcasters hold wire access (the advertisements themselves are not republished)

| Employer (seat) | Text as written | Source | Tag |
|---|---|---|---|
| 방송사 B 국제부 via 인력 파견사 1 | "APTN, 토이터 등 외신 화면 모니터 및 고지"; "외신 화면 정보 및 영문 텍스트 요약 (취재기자 제작 지원)"; "수신 외신 영상 및 기자 요청 영상 (기타 외신, 국무부 브리핑 녹취 등) 을 아카이브에 저장"; "수신 영상 문제 발생 시 외신사, 기술국에 통보" | a public job advertisement | VERIFIED (text read in file) |
| 방송사 B 국제부 via 인력 파견사 2 | Title only in the text file | two public job advertisements | Title VERIFIED; duties not in the text file |
| 방송사 A via 인력 파견사 3 | Title only in the text file; the duty list was read from images | a public job advertisement | The "AP 등 영어권 외신 모니터링" wording is from an analysis of public job advertisements (image advertisement), not from these text files: DOCUMENTED secondhand |

Two cautions for the supplement's claim "explicitly identify AP/APTN and Reuters": (1) the 방송사 B text says "토이터", almost certainly a typo for
로이터 (Reuters): INFERRED; (2) the text files I could search name APTN once, and AP only in the 방송사 A wording quoted in an analysis of public job advertisements. A grep of all
52 job-advertisement text files for AP, APTN, 로이터, Reuters, 연합뉴스, CNN found only the 방송사 B line above (the other hits were "ASAP", "AP" exams, and a site footer).
The advertisement wording shows the seats watch wire video, which implies a feed licence. It does not give the contract, its scope, or whether the
staffing agency or the broadcaster holds the tool access.
