# Multimedia demo — RESULTS (R8, 2026-11-25)

> **Status: Experimental result.** Run on a synthetic test clip; no real broadcast material.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Question served: **D7** (does video belong in the MVP?). This demo shows what is cheap and deterministic on video
*that we are allowed to have*, and what each step costs. It does **not** touch licensed AP/Reuters/broadcaster ingest.

## Clip and licence

| Item | Value |
|---|---|
| Clip | `File:NASA-Kepler-452b-press-release-briefing video.webm` (Wikimedia Commons), a NASA video shown at the 2015-07-23 Kepler press teleconference |
| File page | https://commons.wikimedia.org/wiki/File:NASA-Kepler-452b-press-release-briefing_video.webm |
| Licence | Commons template `{{PD-USGov-NASA}}`, "Public domain" (VERIFIED: wikitext of the file page read through the Commons API, 2026-11-25). Licence reference: https://commons.wikimedia.org/wiki/Template:PD-USGov-NASA |
| Original source | NASA YouTube video `G_zcEgx1IgQ` ("NASA's Kepler Mission Discovers Bigger, Older Cousin to Earth") |
| Local copy | **Not stored in the project** (25 MB). Re-download: `https://upload.wikimedia.org/wikipedia/commons/1/14/NASA-Kepler-452b-press-release-briefing_video.webm` |
| Content | 99.99 s, 1280x720 VP8, Vorbis stereo 44.1 kHz, English narration. Informational, "news-like"; not a live feed |

## How to re-run

```
uv venv .venv && uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe run_demo.py <path-to-kepler452b.webm>      # needs ffmpeg/ffprobe on PATH; GROQ_API_KEY in a .env
```
Tested with ffmpeg 8.1 (gyan.dev full build), scenedetect 0.7.3, Python 3.13.7, Windows 11. Wall time of the whole script: about
one minute.

## Results (all TESTED, files in `out/`)

### 1. ffprobe metadata to JSON (`out/ffprobe.json`)
Container `matroska,webm`, 99.988 s, 25,136,944 bytes, 2.01 Mb/s; video VP8 1280x720 (~59.9 fps nominal); audio Vorbis 44.1 kHz
stereo. The file carries **no editorial metadata** (only an `encoder` tag). A real wire clip would have its slug, shotlist,
dateline and restrictions in a sidecar (NewsML-G2 / ninjs / vendor XML), not in the container. See report 07 section 2.

### 2. Thumbnail strip (`out/thumbstrip.jpg`)
One frame per 10 s, 5x2 tile. I read it: Kepler spacecraft, Cygnus field-of-view diagram, Earth-and-exoplanet animation, launch
footage, NASA Ames end card. Matches the narration.

### 3. PySceneDetect (`out/scenes.csv`)
`ContentDetector(threshold=27)` found **9 scenes**: boundaries at 12.0, 63.5, 67.5, 75.5, 87.4, 89.8, 90.4 and 91.4 s. Coarse:
one 51 s "scene" is a continuous animation with slow camera moves. Usable for key-frame selection and chaptering; not a
substitute for a story-boundary detector. No threshold tuning was done.

### 4. Black / freeze / silence detection, with controls (`out/detector_results.json`)
Filters (parameters: `blackdetect=d=1:pic_th=0.98:pix_th=0.10`, `freezedetect=n=-60dB:d=2`, `silencedetect=n=-50dB:d=1`).
Synthetic 44 s file built from the clip: clean 0-10 s, **3 s black picture** (10-13 s, audio kept), clean 13-19 s,
**3 s digital silence** (19-22 s, picture kept), clean 22-30 s, **4 s frozen frame** (30-34 s, audio kept), clean 34-44 s.

| Control | Result |
|---|---|
| Known answer: black 10-13 s | fired, 10.005-13.005 s |
| Known answer: silence 19-22 s | fired, 19.008-22.043 s |
| Known answer: freeze 30-34 s | fired, 30.045-34.045 s |
| Nonsense (every clean segment x 3 detectors = 12 checks, window trimmed 0.5 s each side) | **0 of 12 fired** |

**Instrument verdict:** it fires on injected faults and stays quiet on clean material, so its null on clean segments is
meaningful (collection-integrity rule 2). Caveats found along the way:

- **A black picture also trips `freezedetect`** (10.005-13.005 s appears in both lists). Black is a static picture. An alert rule
  must treat "black" and "frozen" as one family, or it will double-report.
- **The unmodified source clip contains natural events.** `freezedetect` fired on the real clip at 22.0-32.0 s (a near-static
  animation) and `silencedetect` at 19.75-20.77 s (a natural narration pause). That is correct detector behaviour on legitimate
  content, and it is the main operational lesson: **freeze alone is a weak alert signal on news content** (graphics, slides,
  locked-off shots). The first run of this demo placed its "clean" control over that region and showed a false positive;
  the control plan, not the detector, was wrong. It was corrected and rerun; the flawed first run is kept in
  `out/first_run_flawed_plan/` as evidence. (A second flaw in the first run, an unbounded `loop` filter that hung ffmpeg, was fixed
  with an output `-t`.)
- Detection latency is the minimum duration parameter (`d=`) plus processing; timestamps agree with the injected boundaries to
  within about 50 ms for all three detectors on this file. Not tested on a live stream.

### 5. Groq Whisper ASR to SRT (`out/asr_groq.srt`, raw `out/asr_groq.json`)
Model `whisper-large-v3-turbo`, first 60 s (16 kHz mono FLAC extracted with ffmpeg), `language=en`, `temperature=0`,
`response_format=verbose_json` (Groq's documented formats are json / verbose_json / text, so SRT is built locally from the
segments, which is deterministic). 10 segments, 747 characters. I read the whole SRT against the narration and thumbnails:
it is coherent and correct on this clean studio-quality narration (for example "Kepler-452b is about 60% larger than Earth").
The last cue is cut mid-sentence at the 60 s limit, as expected. An SRT timestamp bug (a cue rendered `00:00:59,1000`)
was found on reading the output, fixed, and the script rerun. **Not tested:** Korean audio, noisy field audio, multiple speakers,
long files, latency. Korean support is not stated on Groq's STT docs page (see report 07).

### 6. YouTube channel RSS discovery test (`out/yt_rss_nasa.xml`)
One request to `https://www.youtube.com/feeds/videos.xml?channel_id=UCLA_DiR1FfKNvjuUpBHmylQ` (NASA's channel), polite UA:
HTTP 200, 26 KB, **15 entries**, each with `yt:videoId`, title, watch link, `published`, `updated`, thumbnail URL,
description. **No duration field.** No API key needed. (Discovery and metadata only; no video downloaded.)

## Limits
- One clip, one speaker, English, clean audio. No Korean test, no live stream, no real wire clip.
- Synthetic faults were injected by re-encoding; real feed failures (SDI loss, encoder stall, partial packet loss) look different.
- No stream-liveness test was run (no stream to test). That mechanism is documented in report 07, not demonstrated.
