# Multimedia and broadcast: standards, delivery and tooling (R8 source log, 2026-11-25)

> **Status: Verified finding.** Standards and delivery formats checked against public documentation.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Companion to [`technology/multimedia-and-broadcast-report.md`](multimedia-and-broadcast-report.md) (which carries the recommendation) and to
[`experiments/multimedia/results.md`](../experiments/multimedia/results.md) (which carries the demo). This file is the evidence log: findings with tags,
sources, and the searches that were run. Every row was checked on **2026-11-25**.

Method note: about 30 searches and fetches (cap). Search-tool answers and the small-model summaries returned by the page
fetcher are second-hand; where a finding rests only on those it is tagged DOCUMENTED at best, and where the primary page
could not be read it says so. AP's developer site (`developer.ap.org`) could **not** be fetched by the tooling
(blocked), so no AP field list was read from AP itself.

## 1. How wire and exchange video reaches a broadcaster

| ID | Finding | Tag | Source |
|---|---|---|---|
| F-H-01 | AP moved video customers from a satellite "Global Video Wire" to **file-based delivery** (AP Media Port, per-story digital files sent as each story is ready; delivery tied into customers' digital newsroom production systems). Old article, undated in the snippet. | DOCUMENTED (trade press, dated years back) | https://www.tvtechnology.com/equipment/ap-launches-filebased-video-news-delivery-service |
| F-H-02 | AP's current integration surface is the **AP Media API** (text, pictures, graphics, video, audio). Access is gated by AP licensing; a third-party catalogue lists a feed endpoint `GET /media/v/content/feed` and says AP publishes no OpenAPI spec. Neither claim read from AP itself. | UNVERIFIED (mirrors and aggregators only) | https://apis.io/apis/associated-press/associated-press-content-api/ ; mirror https://kompas.wasmer.app/https_developer_ap_org/ap-media-api |
| F-H-03 | **AP shotlist, script and restriction fields were not found** in any official source. One 2010s APTN item says material "will come complete with shot lists". | UNVERIFIED-absent. Searches: "AP Newsroom video delivery broadcasters shotlist script restrictions metadata"; "developer.ap.org AP Media API documentation video shotlist"; "AP Newsroom shotlist video restrictions script APTN"; direct fetch of developer.ap.org (blocked) | see searches |
| F-H-04 | AP footage is typically raw; customers edit it, add graphics and voice-over before transmission. | DOCUMENTED (secondary) | https://wikipedia.com/wiki/Associated_Press_TV |
| F-H-05 | **Reuters Connect** is the Reuters platform for video and live; the 2017 launch gave broadcasters up to six concurrent live feeds, integrated into newsroom workflows. **Reuters shotlist/script/restriction fields not found** in any official source. | DOCUMENTED (press release) for the platform; UNVERIFIED-absent for fields. Searches: "Reuters Connect video shotlist script restrictions broadcasters" | https://thomsonreuters.com/en/press-releases/2017/october/reuters-launches-next-generation-live-video-service-for-news-broadcasters-and-digital-publishers.html |
| F-H-06 | **EBU Eurovision News Exchange (EVN)**: about 70 public and private broadcast and content partners (Europe, Asia, Americas). Contributors confirm they own or may share the content; EBU gets a non-exclusive, perpetual right to distribute it to partners for news output. Edited items arrive as file uploads carrying pictures, script and metadata; live feeds use satellite. Since the 2017 rule changes, officially communicated **usage restrictions are mandatory to respect**. No per-field metadata schema was published on the pages read. | VERIFIED for partners count and clearance terms (page fetched); DOCUMENTED (search summary of ebu.ch and trade press) for the delivery mechanics | https://news-exchange.ebu.ch/clearance ; https://www.ebu.ch/news/2017/11/rule-changes-for-eurovision-news-exchange-agreed-by-12th-news-assembly |
| F-H-07 | Consequence for the project: what a clip arrives with is **INFERRED** from the open standards a wire service is likely to use, not read from AP or Reuters: slug/headline, creation date and place, a text shotlist, a text script (shots plus soundbite text), rights/usage terms, duration, format and rendition. | INFERRED from F-H-08 and F-H-09 | n/a |

## 2. Standards (which ones, what they carry, whether they matter for an MVP)

| ID | Standard | What it is / what it carries (this round's reading) | Tag | Source | MVP relevance |
|---|---|---|---|---|---|
| F-H-08 | **NewsML-G2** (IPTC) | XML news exchange. The video quickstart shows `<description role="descrole:shotlist">` (per-shot visual summary), a script description whose role is provider-specific (the example uses `afpdescRole:script`, so **there is no standard script role**), `<rightsInfo>`/`<usageTerms>`, `<located>` (place) and `<contentCreated>`; `<remoteContent>` carries `@duration`, `@durationunit`, `@format`, `@rendition`. No dedicated slugline or dateline element in the video example. | VERIFIED (primary page) | https://www.iptc.org/std/NewsML-G2/2.29/documentation/quickstart-video.html | Naming only. Do not implement XML. |
| F-H-09 | **ninjs** (IPTC "News in JSON") | JSON mapping to NewsML-G2. Latest 3.2 (November 2025), maintained alongside 2.3 and 1.7. Video-relevant fields: `type` ("video"), `slugline`, `language`, `urgency`, `embargoed`, `located`, `subjects`, `genres`, `copyrightNotice`, `copyrightHolder`, `usageTerms`, `rightsInfo`, `digitalSourceType`, and a `renditions` array with `name`, `href`, `contentType`, `duration`, `width`, `height`, `sizeInBytes`, `format`; 3.x adds `aspectRatio`, `frameRate`, `scanType`, `bitrate`, `videoCodec`, `transportProtocol`, `resources` (audio tracks, subtitles). **No dateline property and no audio-codec property.** | VERIFIED for the field list (user guide read; the last 39,000 characters, including the NewsML-G2 mapping section, were not read). DOCUMENTED for version 3.2 date (search result from iptc.org) | https://www.iptc.org/std/ninjs/userguide/ ; https://iptc.org/standards/ninjs/ | **Yes**: use its field names for the item schema. Whether AP's API emits ninjs is **UNVERIFIED** (user guide uses an AP-style example, which is not evidence). |
| F-H-10 | **IPTC Media Topics** | Subject taxonomy, "over 1,200 terms", 13 languages and variants, **Korean is not among them**. Downloads: NewsML-G2 Knowledge Item, SKOS RDF/XML and RDF/Turtle (`cv.iptc.org/newscodes/mediatopic/?format=rdfxml` and `?format=rdfttl`), NewsML 1 topic set, Excel, tree view. Licence: "All NewsCodes vocabularies are copyright IPTC and licenced under the Creative Commons Attribution 4.0 licence" (attribution required, no fee). Update cadence is stated inconsistently: "at least once a year" on the Media Topics page; "every two to three months" in another IPTC-sourced snippet. | VERIFIED (term count, languages, formats, licence quote from primary pages) ; cadence UNVERIFIED (conflict) | https://iptc.org/standards/media-topics/ ; https://iptc.org/std/NewsCodes/guidelines/ | **Yes**: free, machine-readable classification vocabulary. English labels need mapping for Korean output (the LLM can do that). |
| F-H-11 | **IPTC Video Metadata Hub** (and Photo Metadata) | Property set for what is seen and heard (about 20), rights (about 15), administrative (about 15), carried in XMP in the file (or C2PA). Version 1.7 (October 2025) added AI-generated-content properties. Has mappings to NewsML-G2, QuickTime, DPP AS-11, MovieLabs MDDF, MPEG-7. | DOCUMENTED (search summary of iptc.org pages) | https://iptc.org/std/videometadatahub/userguide/ | Later: only if we write metadata back into files. |
| F-H-12 | **EBUCore** (EBU Tech 3293) | Dublin-Core-based metadata set for describing and exchanging audiovisual content (archives, broadcasters). Version found: 1.3 (2011); newer revisions likely exist and were not checked. | DOCUMENTED | https://archive.ert.gr/wp-content/uploads/2016/02/EBU%20Core%20(tech3293v1_3).pdf | No. Archive/MAM interchange. |
| F-H-13 | **MOS protocol** | XML protocol between a Newsroom Computer System (rundowns, scripts, editorial) and Media Object Servers (video servers, still stores, character generators, playout, prompters; the MOS side owns the media objects and their metadata). Latest published spec found: 2.8.5 (document revision 558, 7 September 2017). Vendors (Etere, Cinegy, Vizrt) document MOS bridges to MAM and playout. | DOCUMENTED | https://mosprotocol.com/wp-content/MOS-Protocol-Documents/MOS_Protocol_Version_2.8.5_Final.htm ; https://en.wikipedia.org/wiki/Media_Object_Server | **No.** Only relevant if we plug into a broadcaster's NRCS. We do not have one. |
| F-H-14 | **BXF** (SMPTE ST 2021 family) | XML messages for exchanging schedule, traffic and as-run information between broadcast systems (replaces proprietary vendor interfaces). Parts: ST 2021-1 requirements, -2 protocol, -4 schema. | DOCUMENTED | https://pub.smpte.org/doc/2021/ | **No.** Scheduling/automation. |
| F-H-15 | **Transport**: SDI, SMPTE ST 2110, SRT, RIST, RTMP, HLS | Overview only. SDI/ST 2110 are in-facility (ST 2110 = IP production fabric). SRT (open source, from Haivision) and RIST are the modern internet contribution protocols; RTMP remains the default ingest into streaming platforms; HLS/DASH are viewer delivery formats. | DOCUMENTED (vendor blogs: Wowza, Grabyo; weak sources; ST 2110 comparison thin) | https://www.wowza.com/blog/rtmp-vs-srt-choosing-the-right-protocol ; https://about.grabyo.com/srt-vs-rist-vs-rtmp/ | **No.** Relevant only for a live-feed health monitor, and then only as "what URL can ffprobe open". |

## 3. Processing technology

| ID | Tool | Finding | Tag | Source |
|---|---|---|---|---|
| F-H-16 | ffmpeg `blackdetect` / `freezedetect` / `silencedetect` | Defaults on ffmpeg 8.1: blackdetect `d=2`, `pic_th=0.98`, `pix_th=0.1`; freezedetect `n=0.001`, `d=2`; silencedetect `n=0.001`, `d=2`, optional per-channel `mono`. Each logs start/end events on stderr. Behaviour on injected and clean material: see demo. | VERIFIED (`ffmpeg -h filter=` on the local build) and TESTED (demo) | [`experiments/multimedia/results.md`](../experiments/multimedia/results.md) |
| F-H-17 | PySceneDetect | BSD 3-Clause. Detectors listed on the site: Adaptive, Content, Perceptual Hash, Histogram, Threshold. Version 0.7.3 installed and run on the clip: 9 scenes. | VERIFIED (site) and TESTED | https://www.scenedetect.com/ ; private experiment data (not published) |
| F-H-18 | Hosted ASR (Groq) | `whisper-large-v3` $0.111/h (transcription and translation); `whisper-large-v3-turbo` $0.04/h (transcription only); max file 25 MB free tier, 100 MB dev tier; 10 s minimum billed; formats flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm; response formats json, verbose_json, text (no SRT; build it from `verbose_json` segments). The page does **not** name Korean. | DOCUMENTED (docs page) and TESTED (one English minute, correct) | https://console.groq.com/docs/speech-to-text |
| F-H-19 | Other ASR, OCR, visual search | Deepgram, OpenAI transcription, Google Vision, Claude vision are possible hosted routes. **Not researched this round** (no D7-relevant result expected; recorded as a limit). Local Whisper/faster-whisper/PaddleOCR are not run (project policy (no local model inference)). | UNVERIFIED (not examined) | n/a |
| F-H-20 | MediaInfo, OpenCV, subtitle generation, thumbnails, transcoding | ffprobe already gives container/stream metadata (TESTED); ffmpeg does thumbnails and transcoding (TESTED); SRT is trivial from ASR segments (TESTED). MediaInfo and OpenCV were not run: ffprobe covers the need. | TESTED for ffprobe/ffmpeg; MediaInfo/OpenCV not examined | demo |

## 4. Feed-interruption detection (the "외신사 수신 영상 문제 시 통보" duty)

| ID | Finding | Tag |
|---|---|---|
| F-H-21 | The three ffmpeg detectors fire on injected black (3 s), silence (3 s) and frozen frame (4 s) and stay quiet on 4 clean segments (0 of 12 checks). | TESTED (private experiment data (not published)) |
| F-H-22 | **Black is also "frozen"**: `freezedetect` reports the injected black interval too. | TESTED |
| F-H-23 | **Natural content triggers detectors**: on the unmodified NASA clip, freezedetect reported 22.0-32.0 s (near-static animation) and silencedetect 19.75-20.77 s (a narration pause). Static graphics, slates and locked-off shots are normal on news channels, so a freeze alone is a weak signal. | TESTED |
| F-H-24 | **Stream liveness** (is the feed delivering anything at all): the strongest and cheapest signal is "no new packets or frames for N seconds" on the incoming URL, checked by ffprobe or an ffmpeg `-progress` watchdog with a wall-clock timeout. Not run: there was no live stream to test, and no mechanism was demonstrated. | INFERRED (not tested) |
| F-H-25 | **Mapping to an alerting rule** (a design proposal, not a test result): tier 1 liveness lost for >= N s means "feed down" (page the engineer); tier 2 black >= d1 s or audio silent on all channels >= d2 s means "feed degraded"; tier 3 freeze >= d3 s *while audio is active* means "possible frozen picture", reported only after confirmation over two consecutive windows, with per-source suppression of known slates, bars-and-tone and standby windows. Thresholds must be set per source from a week of real output. | INFERRED from F-H-21 to F-H-24 |

## 5. Media asset management at a glance

| Product | Finding | Tag | Source |
|---|---|---|---|
| Superdesk | "Open source end-to-end news creation, production, curation, distribution and publishing platform" (Sourcefabric), AGPL v3. The README does not say what it does for video, NewsML-G2/ninjs or ingest, so those are unconfirmed here (Workstream C owns it). | VERIFIED (README) for description and licence | https://github.com/superdesk/superdesk |
| Phraseanet | GPL v3 DAM with automatic thumbnails and video transcoding, recommended in listicles for video-heavy archives. | DOCUMENTED (secondary) | https://sourceforge.net/projects/phraseanet |
| ResourceSpace | Open-source PHP/MySQL DAM; licence not confirmed. | UNVERIFIED (licence) | https://openalternative.co/alternatives/resourcespace |
| Implication | A MAM stores and serves media files and their metadata. With no licensed media to store, **a MAM is not on the MVP path**. | INFERRED | n/a |

## 6. Authorised video discovery (metadata only)

| ID | Finding | Tag | Source |
|---|---|---|---|
| F-H-26 | A channel's public RSS feed `https://www.youtube.com/feeds/videos.xml?channel_id=<id>` returned HTTP 200, 15 entries, each with video id, title, link, published, updated, thumbnail, description. **No duration.** No key needed. Anecdotal reports of intermittent 404s on this endpoint exist (UNVERIFIED, forum thread). | TESTED (one channel, one request) | private experiment data (not published) ; https://discuss.ai.google.dev/t/youtube-rss-feed-endpoint-returns-404-errors/113379 |
| F-H-27 | YouTube Data API v3: default allocation 10,000 units/day shared pool; `playlistItems.list`, `videos.list`, `channels.list` cost 1 unit per call; `search.list` is reported on Google's page (as summarised by the fetcher) as its own bucket of 100 calls/day. `videos.list` is the way to get duration. **No key was available to the project: BLOCKED-no-key.** The `search.list` cost differs from older documentation and should be re-read on Google's page before relying on it. | DOCUMENTED (Google page via summariser) | https://developers.google.com/youtube/v3/determine_quota_cost |
| F-H-28 | Broadcaster public pages (YTN, 연합뉴스TV and others) were not examined for video discovery: R5 (sources) owns that, and a robots.txt check per site would be needed first. | UNVERIFIED (not examined) | n/a |
| F-H-29 | Whether automated collection through these routes is permitted for this use is a legal question for R9 (YouTube terms, Korean law). Not assessed here. | UNVERIFIED | n/a |

## 7. Searches and fetches run (for the absence claims)

Searches: ninjs/AP fields; Media Topics licence; AP Newsroom shotlist/script/restrictions (three variants); Reuters Connect
shotlist/restrictions; EVN delivery and clearance; MOS protocol; EBUCore and BXF; IPTC video metadata; transport protocols;
YouTube RSS and quota; open-source MAM comparison. Fetches: ninjs user guide; NewsML-G2 video quickstart; developer.ap.org
(blocked); Ross AP Media Feeds help page (no video metadata on the page); news-exchange.ebu.ch/clearance; Groq STT docs;
ffmpeg filters page (truncated, so local `ffmpeg -h filter=` used instead); Google quota page; Superdesk README; IPTC
Media Topics page; IPTC NewsCodes guidelines; PySceneDetect site; one YouTube RSS request; Commons API (clip search,
file info, wikitext). About 32 in all; demo downloads excluded.
