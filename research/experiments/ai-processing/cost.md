# R7 API spend: ai_processing (2026-11-25)

> **Status: Experimental result.** 
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Instrument: computed per call from `response.usage` (input and output tokens, thinking included in output) multiplied by
the list prices in a cached copy of Anthropic's model table (2026-10-06): Haiku 5.5 $0.10 / $0.50 per MTok in/out,
Sonnet 5.5 $2.00 / $10.00. It was not read from the billing console. Sum of the `cost_usd` fields in `raw/*.json` and
`raw_repeats/*.json`.

| Step | Calls | Spend (USD) |
|---|---|---|
| Smoke test (1 Haiku + 1 Sonnet extraction; cached and reused by the main run) | 2 | included below |
| Main run: base + injection (`run_experiments.py --phase all`) | 104 | 0.9677 |
| Date-schema fix verification (`--phase datefix`) | 14 | 0.1074 |
| Triage noise repeats (`repeat_triage.py`) | 24 | 0.0284 |
| **Total** | **142** | **≈ 1.104** (cap 1.50) |

By model: Haiku 5.5 ≈ $0.07 over 83 calls. Sonnet 5.5 ≈ $1.04 over 59 calls.
