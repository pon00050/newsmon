# Acquisition methods: feeds, conditional requests, change detection, browser automation (R5)

> **Status: Verified finding.** Source-acquisition methods compared against live endpoints on 2026-11-25.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Verified 2026-11-25. Evidence is the live probe (private experiment data (not published)) unless tagged otherwise.

## 1. Order of preference
1. Publisher feed advertised on the publisher's own page (`<link rel=alternate>` or an RSS index page). 36 of 36 such feeds worked.
2. Documented keyless API (Federal Register, SEC, GDELT files, Bluesky public AppView, Mastodon).
3. Generated feed (RSSHub, self-hosted) for sites with no feed: inherits the site's terms, adds a service to run.
4. HTML change detection (sitemap, listing-page diff).
5. Browser automation: last resort, see section 5.

## 2. Discovering feed URLs (and why not to guess)
- Two passes: homepage `link rel=alternate` (`discover_feeds.py`), then each publisher's RSS index page (`discover_feeds_l2.py`). Output: `discovery_results.json`, `discovery_l2_results.json`.
- Results: index pages yielded real feeds for Yonhap (15 section feeds on `/rss/index`), Kyunghyang, SBS, CGTN, CNA Taiwan, CNA Singapore, SCMP, SEC; homepage links yielded Al Jazeera, France 24, Donga, Hankyung, Korea Herald, RFI, VOA Chinese, YouTube channels.
- Some publishers expose nothing machine-discoverable: BBC's feed index is a 2011 stub, Guardian's help page gives a rule ("add /rss to any index URL"), and for KBS, YTN, Hankyoreh, Chosun, Xinhua, Zaobao nothing was found on their pages or by search. For BBC, DW, NPR, Yonhap English and BBC Chinese, feed URLs came from third-party directories (feeder.co, feedspot) and were then probed. A third-party directory can be wrong or stale: one third-party Hankyoreh mirror URL returned 404, and a legacy China Daily path returned 404.
- Control: a bogus path on aljazeera.com returned HTTP 404, so a 404 does mean "no such resource" there. Evidence: TESTED.

## 3. Conditional GET and polite polling
- Observed on 36 live feeds: 21 send validators (13 ETag + Last-Modified, 4 Last-Modified only, 1 ETag only, 3 CNA Taiwan Last-Modified). 18 honoured them with HTTP 304 when sent back; the 3 CNA Taiwan feeds answered 200 with a full body. 15 send no validators (BBC, NPR, DW, France 24, SBS, Donga, Korea Herald, RFI, VOA, BBC Chinese, DW Chinese, SEC EDGAR Atom ...). TESTED.
- Rule for the collector: send `If-None-Match` / `If-Modified-Since` when validators exist; otherwise hash the body (or compare guid sets) to skip parsing; treat `304` as "no change". Dedupe on `guid` where present, otherwise on the link (5 feeds have no guid).
- Etiquette used and recommended: descriptive User-Agent with contact, one request per resource per probe, 1 s between requests to the same run, robots.txt checked per host. SEC asks for a declared User-Agent and max 10 req/s (DOCUMENTED, https://www.sec.gov/about/webmaster-frequently-asked-questions). GDELT's 429 text asks for one request per 5 s (TESTED).
- robots.txt parsing trap (TESTED): Python's `urllib.robotparser` strips a trailing `?` from rules, so `Disallow: /r?` on news.ycombinator.com blocked `/rss`. The known-answer control caught it. The probe uses its own RFC 9309 matcher (longest match, `*` and `$`); do not use `robotparser` for rules that end in `?`.

## 4. Feeds for sites without feeds (RSSHub and alternatives)
- RSSHub: open-source (AGPL-3.0) generator with a route per site. Docs (https://docs.rsshub.app/deploy/, fetched 2026-11-25): Docker Compose recommended, with Redis cache and Browserless for routes that need a browser. DOCUMENTED, not run here.
- Coverage seen: the docs mirror's "traditional media" page lists SBS, KCNA, Rodong Sinmun, SCMP, DW, RFA, RTHK, Ming Pao, Taiwan News among others, and no Yonhap, KBS, YTN, Hankyoreh or Chosun route (only that page was read; Korean routes elsewhere on the site are UNVERIFIED). Most of the outlets the desk cares about already have a native feed, so RSSHub is a fallback for the gaps: Xinhua, People's Daily, KBS, YTN, MBC (robots-disallowed).
- Legal note: a generated feed fetches the same pages, so it inherits robots.txt and terms; it does not make a disallowed site collectable (MBC, Reuters stay out).
- Public RSSHub instances: usage policy not found in the docs page read; prefer self-hosting if used.
- Alternatives (UNVERIFIED, not tested): Google News RSS searches filtered by site (unofficial, third-party reports say Reuters/AP workarounds exist), feed builders (FiveFilters, rss.app). Not recommended as a base because they add a third party between the project and the publisher.

## 5. Change detection as fallback (no feed, robots allow)
- Use in this order: sitemap / news-sitemap (check `robots.txt` for `Sitemap:`; SBS exposes `sitemapRSS.do`) → listing page fetched with a conditional GET → hash of the extracted headline list (title+href), not the raw page (ads and timestamps change every load).
- Anchor on a verifiable field per item (title and URL), because sidebars and recommended rails render other records (project collection rule).
- Applies to: White House news page, China MFA, EU Press Corner (HTML shell only, so a plain fetch sees nothing: these need a documented API or a browser), HKEXnews (3.1 s page).

## 6. When browser automation is justified
- Justified only if all hold: (a) the content is public without login, (b) robots.txt and terms allow automated access, (c) no feed, API or sitemap exists, (d) the content matters to a D-decision.
- Not justified: anything behind a login, CAPTCHA or bot challenge. Observed blocks (apnews.com Cloudflare "Just a moment", state.gov "Technical Difficulties" 403, mk.co.kr 403) are access refusals; the project does not circumvent them.
- Practical: browser automation is also the slowest and most fragile mechanism (RSSHub itself needs Browserless for these routes). For the MVP it is not needed: 36 feeds plus APIs cover the three languages.

## 7. Open questions
- Does the dated KO/ZH feed set stay up over weeks? (7-day poll log.)
- Is the GDELT 15-minute file stream usable for KO/ZH? (not tested; DOC API results inconclusive.)
- Terms for the 12 publishers whose RSS terms were not read.
