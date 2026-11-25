# 04 · Information source and API registry (R5, Workstream D) — decision D2

> **Status: Verified finding.** Deliverable 04. Source probes run on 2026-11-25; terms summaries are not legal advice.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Verified 2026-11-25. Registry rows: [`sources-and-licensing/source-registry.csv`](source-registry.csv) / `sources.json` (88 rows; cite by `source_id`).
Probe: [`experiments/source-collection/probe_sources.py`](../experiments/source-collection/probe_sources.py) → `probe_results.json`, `probe_summary.csv` (77 endpoints on 49 hosts, 3 controls).
Method notes: [`sources-and-licensing/acquisition-methods.md`](acquisition-methods.md). Legal reasoning is R9's: this file only records each source's own wording.

## 1. Answer for D2 (read this first)

**Technically, the open web gives a fast, reliable, keyless feed layer in all three languages. Legally, almost all of it is licensed "personal, non-commercial" only.**
The sources a TV monitoring desk actually uses (AP, Reuters, APTN video) are not collectable by an outside project at all.

| Layer | Verdict | Evidence |
|---|---|---|
| Publisher RSS, EN/KO/ZH | **Works**: 36 of 36 probed live feeds returned 200, median 0.06 s, newest items minutes to hours old | TESTED, `probe_results.json` |
| Terms on that RSS | Yonhap, SBS, Kyunghyang, CNA (Taiwan), CNA (Singapore), Guardian each say personal / non-commercial only | DOCUMENTED, `terms_url` per row |
| Government and disclosures | SEC, Federal Register keyless and open; State Dept blocked (403); korea.kr RSS **discontinued 2026-07-01** | TESTED / DOCUMENTED |
| AP, Reuters | No usable public feed; Reuters robots prohibits automated collection; AP 403 | VERIFIED / TESTED |
| Keyed news APIs (Naver, NYT, NewsAPI, Guardian, DART, YouTube) | All need keys; none held | BLOCKED-no-key |
| GDELT | EN works (open licence incl. commercial, cite GDELT); KO/ZH **not established** (429s, empty results) | TESTED-partial |

**Consequence for D3.** A *foreign-news desk assistant* can run on public feeds for private, single-seat use (links, headlines and short summaries, nothing redistributed), but cannot replace the AP/Reuters wire the seat monitors; the customer's own wire contract has to supply that. A *client clipping service* that redistributes Korean press text is not supported by any open source here: the Korean publishers' RSS terms forbid it, and BIGKinds forbids reproduction. That path needs licences (R2/R9 question).

## 2. Recommended MVP source set

Rule applied: keyless, TESTED-ok, `robots_allows=y`, and terms that do not obviously forbid *private internal use of headline + link + short summary*. "Terms: personal/non-commercial" sources are included **conditional on R9 clearing private internal use**; the MVP must store link + title + summary, not republish article text. If R9 says no, drop to the "clean core" rows.

### 2a. Clean core (open licence or government publication)
| source_id | Why | Caveat |
|---|---|---|
| `sec_edgar_atom_8k`, `sec_data_submissions`, `sec_pressreleases` | SEC FAQ: free to reuse, 10 req/s, declare UA. 40 filings per Atom call in 0.34 s. | English only; financial use case, not core monitoring |
| `fedreg_api` | Keyless JSON: title, abstract, document_number, html/pdf URL, agencies | US federal register only |
| `gdelt_doc_en`, `gdelt_lastupdate` | Open licence incl. commercial with citation; 15-min file cadence observed | DOC API 10-29 s per call and 429s: use the 15-min files, not the API, for volume. KO/ZH unproven |
| `un_press` | Press-release RSS, 304 works | Terms not read (UNVERIFIED) |

### 2b. Feed layer for the desk assistant (private use; terms say non-commercial)
| Lang | Pick (`source_id`) | Reason |
|---|---|---|
| EN | `guardian_world`, `bbc_world`, `aljazeera_all`, `dw_en_all`, `france24_en`, `cna_sg_all`, `npr_news`, `scmp_world` | Fresh (0.07-8 h), 10-144 items, guid + date present. Guardian, Al Jazeera, CNA give 304. BBC feed URL rests on third-party directories (BBC's own page is a stub) |
| KO | `yna_news`, `yna_intl`, `yna_nk`, `khan_total`, `donga_intl`, `hankyung_intl` | Yonhap: 120 items, 0.06 h old, 304 works, but **terms forbid commercial use** (no summary beyond 57 chars). Donga/Korea Herald lack guid: dedupe on link. Hankyung gives titles only. SBS has near-full text (3-4 KB) but terms and footer forbid reuse and AI training: **exclude from MVP** |
| ZH | `rfi_zh`, `voa_zh`, `bbc_zh_simp`, `dw_zh_all`, `cna_tw_intl`, `cna_tw_mainland`, `scmp_china`, `cgtn_china` | CNA Taiwan only serves title/lead/link and says so; it ignores conditional requests (re-downloads). **No Xinhua, People's Daily, China Daily or Zaobao feed was found** on their pages (UNVERIFIED-absent) |
| Social (optional) | `bsky_authorfeed`, `mastodon_tag` | Keyless; Bluesky keyword search is 403 without auth. Terms UNVERIFIED |

Starting volume check (INFERRED from probes): about 24 feeds polled every 5 minutes is under 300 small requests per hour, each 0.02-1 s.

### 2c. Not in the MVP, and why
| source_id | Reason | Tag |
|---|---|---|
| `reuters_home` | robots.txt notice: automated collection prohibited without written consent; public RSS reported dead since June 2020 | VERIFIED / UNVERIFIED (third-party) |
| `ap_home` | 403 Cloudflare challenge; no feed advertised; apnews.com RSS reported stopped 2024 (third-party only) | TESTED / UNVERIFIED |
| `mbc_home` | robots `User-agent: * / Disallow: /` | VERIFIED |
| `yt_ap`, `yt_reuters`, `yt_kbs`, `yt_ytn`, `yt_cgtn` | Channel ids were discovered from the channel pages, but youtube.com robots.txt disallows `/feeds/videos.xml`; not fetched. The Data API needs a key. Video MVP depends on D7 | VERIFIED |
| `reddit_worldnews` | robots `Disallow: /` | VERIFIED |
| `state_gov_rss_index` | 403 "Technical Difficulties" for robots.txt and the page; the seat archives State briefings, so this is a real gap | TESTED |
| `korea_kr_notice` | 정책브리핑 RSS service discontinued (notice dated 2026-07-01); body not read | TESTED |
| Naver, NYT, NewsAPI, Guardian Open Platform, DART, YouTube Data | keys needed, none held | BLOCKED-no-key |
| `bigkinds_home` | login, articles protected by copyright law, reproduction prohibited | DOCUMENTED |

## 3. Findings

### F-D-01 · Publisher RSS is technically excellent in all three languages
- Finding: 36 feeds (18 EN, 11 KO, 7 ZH) all returned 200 in 0.017-0.95 s (median 0.06 s). 18 returned 304 on conditional GET; 15 send no validators; 3 (CNA Taiwan) send Last-Modified but ignore it. 5 feeds lack guid (Korea Herald, Donga x2, Hankyung x2).
- Evidence: TESTED, private experiment data (not published) (2026-11-25).
- Limits: one snapshot, not a reliability time series. Latency was measured from one Windows machine.
- Implication: polling cost is negligible; reliability over weeks is unmeasured (round-2 offer: 7-day poll log, low cost).

### F-D-02 · The Korean and Chinese-language feeds that work say "personal / non-commercial"
- Finding: Yonhap (비상업적 블로그와 개인적 용도로만; 사전 서면 허가 없는 상업적 이용 금지), SBS (개인 이용자의 비상업적 사용에만), Kyunghyang (개인적인 구독 목적; 영리 행위는 사전 허락), CNA Taiwan (個人、非營利組織之非商業用途), CNA Singapore and Guardian (personal, non-commercial). Not read: BBC, Al Jazeera, DW, France24, NPR, SCMP, CGTN, RFI, VOA, Donga, Hankyung, Korea Herald.
- Evidence: DOCUMENTED, `terms_url` per registry row; snippets in private experiment data (not published).
- Implication: D2 cannot treat these feeds as licensed commercial inputs. R9 to decide whether a private single-user monitoring tool is within "personal use".

### F-D-03 · AP and Reuters are not collectable
- Finding: Reuters robots.txt prohibits automated collection without prior written consent; AP returned a 403 challenge to a descriptive-UA request. Third-party sources (feeder.co, FiveFilters, tt-rss forum) report Reuters RSS ended June 2020 and apnews.com RSS stopped in 2024; neither company's own statement was found.
- Evidence: VERIFIED (robots), TESTED (403), UNVERIFIED (end-of-feed dates; searches: "Associated Press official RSS feeds discontinued", "Reuters RSS feeds discontinued 2020").
- Implication: the seat's core input (AP/Reuters/APTN) must come from the client's own contract; the MVP cannot assume it.

### F-D-04 · YouTube channel RSS is robots-disallowed
- Finding: channel ids for AP, Reuters, KBS News, YTN and CGTN were discovered from channel pages (`link rel=alternate`), but robots.txt contains `Disallow: /feeds/videos.xml` for `*`. Not fetched.
- Evidence: VERIFIED, https://www.youtube.com/robots.txt (2026-11-25).
- Implication for D7: video discovery via RSS is not clean; the Data API needs a key and has its own ToS.

### F-D-05 · GDELT: EN works, KO/ZH unproven, API slow and rate-limited
- Finding: DOC 2.0 EN returned 10 articles (29 s). A Korean query returned empty JSON; the Chinese query and later KO/nonsense queries got HTTP 429 even at 10-15 s spacing (the 429 text asks for one request per 5 s, but calls themselves take 10-29 s). GEO API returned 404 on two variants; TV API returned "Invalid query start date" for two timespan forms. `lastupdate.txt` works and supports 304; its timestamp (20261125050000) shows the 15-minute cadence.
- Evidence: TESTED, `probe_results.json`, `gdelt_results.json`. Nonsense control did not complete (server disconnect, then 429), so an empty KO result cannot be read as "no Korean coverage".
- Implication: use the 15-minute files for any GDELT dependency; do not rely on DOC for KO/ZH until validated (round-2).

### F-D-06 · Controls
- Known-answer: Hacker News RSS returned 30 items. It was first reported "robots-disallow" because Python's `urllib.robotparser` strips the trailing `?` of `Disallow: /r?` and so blocked `/rss`; the control exposed the bug and the probe now uses its own RFC 9309 matcher (self-tested). 10 endpoints are marked not-fetched under the corrected matcher.
- Nonsense: a bogus path on aljazeera.com returned HTTP 404 (not a 200 empty feed), so a 404 here means "no such feed". The GDELT nonsense control failed to run (see F-D-05).
- Limit: robots 403/401 responses (state.gov, Guardian API host) were treated as "no rules found" and the page was requested once; state.gov then returned 403.

## 4. What was not established
- 7-day uptime and burstiness of any feed (one snapshot only).
- Terms for 12 feed publishers listed in F-D-02, and for Bluesky/Mastodon API use (UNVERIFIED).
- Feeds for Xinhua, People's Daily, China Daily (legacy path 404), Zaobao, KBS, YTN, MBC, Hankyoreh, Chosun, JoongAng, Maeil Business, Joongang Daily, ABC (AU), UN News, WHO, White House, China MFA, HKEX, EU Press Corner: none found on their pages or by search (UNVERIFIED-absent; instrument validated only for sites where a known feed was found). KBS, YTN, Hankyoreh, Chosun searches returned no publisher page; Mk.co.kr returned 403.
- Key-gated APIs: quotas and terms for Guardian, NYT, GNews, NewsData, Mediastack, Event Registry, Naver, DART (BLOCKED-no-key / UNVERIFIED). The Naver and Guardian documentation pages could not be fetched with the tools available.
- BBC (EN and ZH), DW (EN and ZH), NPR and Yonhap English feed URLs come from third-party directories, but every one returned a live feed when probed.

## 5. Open items for other agents
- R9: decide whether private internal use of RSS headline/summary falls within each publisher's "personal" wording; check YouTube RSS robots issue; Common Crawl ToU; Bluesky/Mastodon API terms.
- R8/D7: video sourcing without RSS or keys.
