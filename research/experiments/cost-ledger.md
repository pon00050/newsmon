# Cost ledger — round 1 (2026-11-25)

> **Status: Experimental result.** Spend on the research experiments, computed from API usage fields, not from a billing console.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

API spend only, merged from each agent's own `COST.md`. The figures are self-reported from token counts and published
rates, not read from a provider billing meter.

| Area | Agent | Provider / model | Spend (USD) | Source |
|---|---|---|---|---|
| AI processing experiments | R7 | Anthropic Haiku 5.5 + Sonnet 5.5 (142 calls) | ≈ 1.104 | [`experiments/ai-processing/cost.md`](ai-processing/cost.md) |
| Event-clustering gold labels + embeddings | R6 | Anthropic Sonnet 5.5; OpenAI text-embedding-3-small | ≈ 0.21 (≤ 0.45 if the Sonnet price was double the assumed one) | [`experiments/event-clustering/cost.md`](event-clustering/cost.md) |
| Multimedia ASR demo | R8 | Groq whisper-large-v3-turbo | ≈ 0.002 | [`experiments/multimedia/cost.md`](multimedia/cost.md) |
| Source probes | R5 | none | 0 | [`experiments/source-collection/cost.md`](source-collection/cost.md) |
| Component smoke tests | R4 | none | 0 | [`experiments/component-smoke/cost.md`](component-smoke/cost.md) |
| Repository trials | R3 | none | 0 | [`experiments/repository-trials/cost.md`](repository-trials/cost.md) |
| **Total** | | | **≈ 1.32 (≤ 1.56)** | |

Agent token costs (orchestration and research agents) are not API spend in this sense and are not recorded here.
