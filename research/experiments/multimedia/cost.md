# COST — R8 multimedia (2026-11-25)

> **Status: Experimental result.** 
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

| Item | Provider | Quantity | Cost | Basis |
|---|---|---|---|---|
| Whisper ASR (3 identical runs of the demo script; 1st and 2nd runs reached the ASR step, 3rd was the final) | Groq `whisper-large-v3-turbo` | 3 requests x 60 s audio | about $0.002 | $0.04 per audio hour, 10 s minimum billed (https://console.groq.com/docs/speech-to-text, checked 2026-11-25). Computed, not read from a billing meter. |
| Everything else | ffmpeg, ffprobe, PySceneDetect, Wikimedia Commons, YouTube RSS | local / free | $0 | |

**Total API spend: about $0.002** (cap $0.50). Claude vision, OpenAI and Anthropic APIs were not used.
Agent tokens are not included here.
