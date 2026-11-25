# 07 — Multimedia and broadcast workflows (Workstream H, round 1, 2026-11-25)

> **Status: Experimental result.** Deliverable 07. Tested on a synthetic clip only.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Decision informed:** D7, video and broadcast in the MVP or deferred.
**Evidence:** [`technology/multimedia-standards-and-delivery.md`](multimedia-standards-and-delivery.md) (finding IDs F-H-nn, source URLs, searches run) and
[`experiments/multimedia/results.md`](../experiments/multimedia/results.md) (the demo, with controls). This was a capped workstream (about 30 searches and fetches,
one demo, about $0.002 of API spend).

## 1. Recommendation for D7

**Defer licensed broadcast video from the MVP. Keep the MVP *video-ready* and let it carry *video-adjacent text* and
public-video *metadata pointers*.** Concretely:

| In the MVP | Why |
|---|---|
| **Item schema that can hold a video item**: `type` (text, video, audio, picture), `slugline`, `located`, `language`, `urgency`, `usageTerms`/`rightsInfo`, `subjects`, and a `renditions` list (`href`, `contentType`, `duration`, `width`, `height`), using **ninjs field names** | Costs nothing now, and avoids a schema migration when video arrives (F-H-09). |
| **Text that rides with video is ordinary text**: shotlists, scripts, captions, transcripts | The seats' stated duties include summarising and translating English text and archiving briefing transcripts (an analysis of public job advertisements section 2), which are text. The text pipeline serves them with no media handling. |
| **Video *discovery* by metadata only**, from authorised public sources, starting with YouTube channel RSS (TESTED: HTTP 200, 15 entries, title, link, dates, thumbnail, description, no duration, no key) | Gives the system "a clip exists, here is its title and date" with no download, no transcoding and no storage. Legal permission is R9's question (F-H-29). |
| **IPTC Media Topics (CC BY 4.0, SKOS download) as an optional subject vocabulary** for classification | Free and machine-readable (F-H-10). English labels only; no Korean. |

| Deferred (not MVP) | Why |
|---|---|
| **Licensed AP, Reuters, EVN or broadcaster video ingest** | No access this round; licensing and delivery are contractual. Field lists could not be read from AP or Reuters (F-H-03, F-H-05). Nothing to build against or test. |
| **MOS, BXF, EBUCore, SDI, ST 2110, MAM** | These connect to a broadcaster's own newsroom and playout plant (F-H-13, -14, -15). We have no plant to connect to. |
| **Feed-health monitor as a product feature** | Demonstrated at the detector level (section 4), but it needs a live incoming feed to watch. The only people who have one are the broadcasters. |
| **Scene detection, visual classification, OCR, multimodal search** | Scene detection works but is coarse (9 scenes on a 100 s clip); no D7-relevant evidence that these change what an MVP user does. |
| **Continuous or live ASR of broadcasts** | Cost is small, but without licensed or authorised broadcast audio there is nothing to feed it, and Korean accuracy is untested. |

**Optional stretch, only if D3 chooses the foreign-desk assistant:** *on-demand* transcription of a **public** clip (for example
a State Department briefing video on an authorised channel) with hosted Whisper, producing a timestamped transcript that
enters the text pipeline. Demonstrated here for one English minute at about a thousandth of a cent per second of audio
(Groq `whisper-large-v3-turbo` $0.04 per hour). It is a post-MVP task, not a gate.

**Why defer rather than include.** Three reasons, in order of weight. (1) The decisive blocker is access, not technology: the
only video the seat actually handles is licensed wire video and a broadcaster's own receiving feeds, and neither is available to
build or test against. (2) The tested technology is cheap and works, so nothing here argues that video is *hard*; it argues
that video has no *input*. (3) The text, dedup, clustering and delivery work that D1 to D6 and D8 decide is needed whether or not
video exists, and video items can reuse it once they are described as items.

**What would change this recommendation:** a broadcaster or agency giving this project a legitimate feed or API account; D3
selecting a use case where video is the product (for example monitoring a channel for a client); or a round-2 test showing hosted
ASR on Korean broadcast audio is accurate enough to make "searchable broadcast transcripts" the headline feature. Any one of
these moves video into the MVP as the first video slice: ingest, ASR, text pipeline.

## 2. What arrives with a wire video clip (and what could not be established)

- **Established (VERIFIED, NewsML-G2 video quickstart):** an open-standard video item carries a headline, a place and creation
  date, a per-shot **text shotlist**, a **text script** (the example's role is vendor-specific, so there is no standard script
  role), `usageTerms` (rights), and for each rendition `duration`, `format` and a rendition name (F-H-08).
- **Established (VERIFIED, ninjs user guide):** the JSON equivalent adds `slugline`, `urgency`, `embargoed`, `rightsInfo`,
  `digitalSourceType`, and 3.x renditions with `frameRate`, `bitrate`, `videoCodec`, audio-track and subtitle `resources`.
  There is **no dateline property and no audio-codec property** (F-H-09).
- **Not established (UNVERIFIED-absent):** the actual AP and Reuters field lists, including their "restrictions" fields.
  `developer.ap.org` could not be fetched, and no official page was found for Reuters Connect (F-H-03, F-H-05). So "AP ships
  slug, dateline, shotlist, restrictions, duration, format" is the brief's expectation and is **INFERRED** from the open
  standards, not read from AP. Whether AP's API emits ninjs is also unverified. Round 2 would need an AP or Reuters
  developer account or a sales contact to settle this.
- **Established (VERIFIED, EBU page):** EVN has about 70 partners; contributors warrant their rights; **officially
  communicated restrictions must be respected** (2017 rules); edited items arrive as uploads of pictures, script and
  metadata, live feeds by satellite (F-H-06). The restrictions concept is real at the exchange level; its field format
  was not found.
- **Implication for schema:** model *restrictions* as a first-class field on any video item even though we cannot yet say
  what the vendors call it. A clip with an unknown restriction should be treated as restricted.

## 3. Standards: which matter for an MVP

| Matters (adopt names, no implementation) | Does not matter for an MVP |
|---|---|
| **ninjs** field naming (F-H-09) | NewsML-G2 XML (ninjs is its JSON form) |
| **IPTC Media Topics** vocabulary (F-H-10) | EBUCore, IPTC Video Metadata Hub (only if writing metadata into files) |
| | **MOS** and **BXF** (broadcaster plant integration) |
| | **SDI, ST 2110, SRT, RIST, RTMP, HLS** (transport; ST 2110 is in-facility, SRT/RIST are contribution links) |

## 4. Processing: what the demo showed (TESTED)

Clip: a NASA video (public domain, `{{PD-USGov-NASA}}` on Wikimedia Commons), 100 s, English narration. Full detail and files
in [`experiments/multimedia/`](../experiments/multimedia)`.

| Step | Result | Cost |
|---|---|---|
| ffprobe to JSON | Container, codec, duration, resolution, bitrate extracted in one command. No editorial metadata in the file. | free, local |
| Thumbnail strip | One 5x2 contact sheet from one ffmpeg command; read and matches the content. | free, local |
| PySceneDetect | 9 scenes; coarse on slow animation. | free, local |
| black / freeze / silence detection | **Known-answer: 3 of 3 injected faults fired** (black 10-13 s, silence 19-22 s, freeze 30-34 s, boundaries within about 50 ms). **Nonsense control: 0 of 12 checks fired** on clean segments. | free, local |
| Groq Whisper (`whisper-large-v3-turbo`), 60 s | Correct, readable English transcript, 10 timed segments, SRT built locally. | about $0.0007 per minute of audio |

**Operational lessons from the controls**, relevant to anyone building a feed monitor (and to the seat duty "tell the wire or
engineering when the incoming feed breaks"):

1. **Black also trips freeze.** One failure, two detectors; the alert rule must merge them.
2. **Freeze alone is a weak signal on news content.** The unmodified source clip contained a 10 s near-static animation that
   `freezedetect` correctly flagged. Slates, graphics and locked-off shots look the same on a real channel.
3. **The detectors need a real feed to be calibrated.** Thresholds (`d=`, noise tolerance) have to be set per source from
   observed output. The demo thresholds are not recommendations.
4. A dedicated, stronger signal is **stream liveness** ("no packets for N seconds"). It was not tested (no live stream
   existed). It is documented here only as a design (F-H-24).

**Mapping to an alerting rule (design, INFERRED, F-H-25):**

| Tier | Condition | Action |
|---|---|---|
| 1, feed down | no packets or frames for N s | alert engineering/wire contact immediately |
| 2, degraded | black >= d1 s, or silence on all channels >= d2 s | alert, with the timestamp and a thumbnail |
| 3, possible frozen picture | freeze >= d3 s **while audio is active**, confirmed over two windows | low-confidence alert; suppress known slates and standby windows |

## 5. Limits of this workstream

- One clip, English, clean audio. **No Korean ASR test** (Groq's page does not name Korean; Whisper's Korean quality on
  broadcast audio, with music beds and overlapping speech, is unmeasured here). A round-2 test of one Korean public clip
  would cost about $0.01 and a few minutes.
- No live stream, no licensed clip, no real feed failure. Synthetic faults only.
- AP and Reuters field lists not read from the source (section 2). Stream-liveness mechanism not run.
- Deepgram, OpenAI transcription, Google Vision, Claude-vision OCR, MediaInfo and OpenCV were not examined: no result there
  could change D7 given the access blocker.
- Superdesk's media handling and the other open-source MAMs were looked at only at README or listicle level (Workstream C owns
  them).
- Legal permission to collect from YouTube or broadcaster pages, and robots.txt for broadcaster sites, were not assessed
  (R9 and R5).

## 6. Hand-offs to other workstreams (not acted on)

- **R9 (legal):** YouTube terms for RSS and API use; EBU/EVN and wire-service redistribution terms; Korean broadcast-clip rights;
  the finding that EVN restrictions are mandatory.
- **R5 (sources):** whether Korean broadcasters publish public video pages or channels with RSS; YouTube channel IDs of the
  channels the seats resemble; the YouTube RSS 15-item window and the missing duration field.
- **R6 (data model):** adopt ninjs naming for items, a `type` field, a `renditions` list, and `restrictions` as first-class.
- **R7 (AI):** hosted ASR cost ($0.04 to $0.111 per hour at Groq) and the Korean-quality test as a possible round-2 item.
- **R1 (business processes):** the "text rides with the video" point (shotlist, script, transcript are text) may reshape what
  "video work" means at the desk.
