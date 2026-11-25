# Cost — R4 component smoke (2026-11-25)

> **Status: Experimental result.** 
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

API spend: **$0.00**. No Anthropic, OpenAI or Groq call was made. All fetches were public RSS/HTML/registry/PyPI/GitHub
endpoints without keys. Request footprint: BBC feed 1 + 1 article; Yonhap feed ~6 (httpx, feedparser x2 in smoke, reader x2,
feedparser x2 in supplement) + 1 article + robots.txt; PyPI RSS 2 (control); MCP registry 14 queries. Spend of agent tokens is
not recorded here.
