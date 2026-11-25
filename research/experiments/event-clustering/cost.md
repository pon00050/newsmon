# R6 API spend (2026-11-25)

> **Status: Experimental result.** 
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

All R6 API calls are recorded here. The cap for R6 was $2.00.

| When (UTC) | Step | Provider / model | Usage (from the API response) | Cost | How the cost was computed |
|---|---|---|---|---|---|
| 2026-11-25 ~05:05 | Embed 826 corpus items (`cluster_experiment.py embed`) | OpenAI `text-embedding-3-small` | 113,167 tokens | ~$0.002 | 113,167 × $0.02 per 1M tokens (OpenAI list price as I know it; not re-checked today) |
| 2026-11-25 ~05:06 | Propose gold event labels for 240 items in one call (`cluster_experiment.py label`) | Anthropic `claude-sonnet-5-5` | 32,223 input, 7,313 output tokens (3,166 of them thinking) | ~$0.21 | Assumes $3 in / $15 out per 1M tokens, the Sonnet tier price. **UNVERIFIED for 5.5.** At twice that price it would be $0.42. |
| — | Model list (`GET /v1/models`) | Anthropic | — | $0 | — |

**Total: about $0.21 (at most about $0.45 even if the Sonnet 5.5 price is double the assumed one).** No other paid calls were made.
GDELT, the RSS feeds and the trafilatura page fetches cost nothing.
