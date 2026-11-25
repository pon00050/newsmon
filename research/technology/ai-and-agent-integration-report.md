# 06 · AI and agent integration report (R7, 2026-11-25)

> **Status: Experimental result.** Deliverable 06. Measured on small samples; prices were those of 2026-11-25 and must be re-checked.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Informs **D6** (where AI is used, which provider, how the system degrades without it) and **D8** (the MCP part of the
delivery surface). Evidence tags follow [`evidence-conventions.md`](../evidence-conventions.md), and every fact is dated 2026-11-25 unless stated.
Experiments: [`experiments/ai-processing/`](../experiments/ai-processing) (`RESULTS.md`, `metrics.json`, `raw/`). Companion files:
[`technology/mcp-tool-design.md`](mcp-tool-design.md) and [`technology/ai-threat-model.md`](ai-threat-model.md).

## 0. Recommendation in one screen

1. **AI belongs in one place in the MVP:** a **single, tool-less, schema-constrained LLM call per item** that does
   translation, the Korean summary, the who/what/where/when extraction and claim attribution together. It is preceded by
   a cheaper triage call on the title and lead. Everything else in the pipeline (collection, dedup, clustering, search,
   alerts, feed health) is deterministic code.
2. **Provider: Anthropic.** Use `claude-haiku-5-5` for triage and bulk enrichment, and `claude-sonnet-5-5` only for
   briefings and on-demand analysis. Measured per-item cost: Haiku extraction **$0.0013**, Haiku triage **$0.0003**,
   against Sonnet's $0.0275 and $0.0062 (TESTED). At 1,000–3,000 items a day, the Haiku-routed pipeline costs about
   **$1–5 a day**. Sending everything to Sonnet would cost about **$30–100 a day**.
3. **Degradation:** when the LLM is unavailable, collection, dedup, FTS search, keyword or watchlist alerts and feed-health
   alarms keep working. Items show raw text marked "AI 처리 대기", and enrichment drains from a queue when the provider
   returns. AI is an enrichment layer, never a gate.
4. **No RAG or vector store in the MVP.** BM25/FTS5 plus filters, with an LLM that rewrites the query across languages
   and answers over the top-k with citations, is enough. Add embeddings only if R6's dedup or clustering experiments need
   them.
5. **No runtime agents and no multi-agent design.** Expose a **read-only MCP server** (search_articles, get_article,
   get_event, list_events, list_alerts, get_briefing, get_feed_status, list_sources) so that the user's own Claude
   Desktop or Code can act as the agent.
6. **Security posture (TESTED):** tool-less schema-constrained calls were **not hijacked** in 0/24 attempts. A subtle
   "editor's note" **did push relevance scores up** (+22.6 mean on Haiku, +8 on Sonnet) **while the model flagged the
   injection**. The pipeline must therefore act on `injection_suspected` deterministically (human review, the model's
   score ignored). It cannot trust the score.

## 1. Capability matrix (question 1)

Levels: (1) no AI · (2) conventional NLP model · (3) single LLM call · (4) structured multi-step workflow ·
(5) autonomous or semi-autonomous agent. **Default to the lowest level that works.** Level 2 is rarely chosen here,
because the workspace forbids local inference, so a "conventional model" would mean another cloud vendor for a job the
level-3 call already does in the same request.

| Capability | Level | Why this level | Main failure modes | Verification | Evidence |
|---|---|---|---|---|---|
| Language detection | **1** (feed metadata, script heuristics); the LLM also returns it at no extra cost | Deterministic is enough | Mixed-script items | LLM value vs heuristic disagreement → review | TESTED: LLM 11/11 correct |
| EN/ZH → KO translation (gist, summary, key quotes) | **3**, inside the enrichment call | Translation is needed for context, not as a separate product. One call is cheaper than an MT API (§3) | Wrong name transliteration, changed numbers, dropped hedges or attribution | Numbers in the source must appear in the output (regex); `name_original` must be verbatim in the source; the original text is kept next to every translated quote; a human checks anything that goes on air | TESTED: correct transliterations (천지닝, 천시) on the ZH sample; verbatim grounding 98–100% |
| KO/ZH → EN | **3**, same call shape | Same | Same | Same | INFERRED from the EN/ZH→KO result (not separately tested) |
| Summarisation (Korean news style) | **3** | A single call does it well | Facts added; attribution dropped | Hangul-ratio check; claims carry `attributed_to`; spot review | TESTED: 22/22 Korean summaries |
| Structured extraction (who, what, where, when, entities) | **3** with JSON Schema | Structured outputs gives a guaranteed shape; the meaning is checked locally | Partial or invented dates; paraphrased entity names | Pydantic constraints + `format: date` + `precision` field; verbatim grounding | TESTED: v1 failed 2/11 and 1/11 on dates; v2 passed 14/14 |
| Editorial relevance against a desk profile | **1 + 3**: rules first (watchlist terms, source priors, NK/US/CN keyword hits), then Haiku triage | Rules are explainable and immune to injection. The LLM adds judgement on items the rules miss | Score noise (±15 on repeats); manipulation by planted "editor's notes" | Coarse bands (drop / review / report / flash), never fine cut-offs; a flagged item is excluded from automatic scoring; periodic agreement check against desk choices | TESTED: noise 35–62 on 5 repeats; A2 attack +22.6 |
| Claim extraction with attribution | **3** (field of the extraction schema) | It falls out of the same read | Unattributed claims presented as fact | `attribution_type` enum; "unattributed" claims are highlighted | TESTED in schema; quality checked on one full read |
| Contextual analysis ("why this matters to Korea") | **3**, Sonnet, **on demand or for briefing items only** | Valuable but speculative, so it should not run on every item | Speculation presented as fact | Labelled "AI 분석"; never mixed with summary fields | INFERRED |
| Related-development linking | **1/2**: R6's deterministic dedup and clustering (MinHash, TF-IDF, entity overlap); cloud embeddings only if R6 shows a need; **3** only to name a cluster or adjudicate borderline merges | Deterministic code is cheap, reproducible and immune to injection | Over- or under-merging | R6's experiments | Pointer to R6 (D5) |
| Conflicting-report comparison | **4**: cluster (1/2) → per-article claims (already extracted) → deterministic alignment on entity, number and date → LLM compares only the candidate pairs (3) → human | The parts are simple; the risk is the LLM inventing a conflict, so it sees only aligned pairs | False conflicts from translation differences | Shows both original sentences side by side; the human confirms | INFERRED; built from the TESTED claim fields |
| Briefing generation (morning and evening editions) | **4**: selection by rules over bands and event size (1) → Sonnet writes with `cited_article_ids` (3) → code checks every citation exists in the selected set → human approves | The quality bar is high and the output is read by many people; Sonnet's richer synthesis is worth the cost a few times a day | Uncited claims; one source over-weighted | Citation existence check; every bullet must cite ≥ 1 ID; review queue | INFERRED (Sonnet's quality edge TESTED on extraction) |
| Natural-language search | **1 + 3**: FTS5/BM25 + filters (1); the LLM rewrites the question into KO/EN/ZH keywords and filters (3); optionally an LLM answer over the top-k with citations (3) | Cross-lingual recall is the real problem, and keyword expansion solves most of it without vectors | Hallucinated answer; missed recall | The answer cites `article_id`s; the citations are checked; raw hits always shown | INFERRED (§6) |
| Research assistance ("trace how X evolved this month") | **5**, single semi-autonomous agent with read-only tools and a step budget. **Deferred past MVP** | The only open-ended task where the path is unknown in advance. A human reads the result, so errors can be recovered | Wandering, cost, injection through retrieved text | Read-only tools, no outbound tools, step and $ budget, citations | INFERRED. Via MCP the user's Claude Desktop already provides this |
| Image and video-frame understanding | **1 + 3**: ffmpeg scene detection selects frames (1); a cloud vision LLM describes or OCRs only the selected frames (3). **Deferred (D7, R8)** | Frame selection is deterministic; vision calls are expensive per frame | OCR errors on chyrons; misidentified people | Never names people from the face alone; human check | Pointer to R8 |
| Feed-break detection (desk duty: notify the wire or engineering) | **1** | Error streaks and items-per-hour against baseline are arithmetic | — | Alert test | INFERRED |

## 2. Engineering patterns (question 2)

### F-G-01 · Structured outputs guarantee shape, not meaning: validate locally in three layers
- Finding: with `output_config.format` (JSON Schema) there were **0 JSON-parse failures and 0 refusals in 142 calls**. Yet
  2/11 (Haiku) and 1/11 (Sonnet) outputs broke the intended date contract, because the API schema cannot carry `pattern`,
  `minimum` or `maxLength`. The fix: model the uncertainty in the schema (a `precision` enum, a `date_exact` field as
  `anyOf[format: date, null]`, separate year and month fields) and pass trusted metadata (the publication date) in the
  prompt. After the fix, **14/14 passed**.
- Evidence: TESTED, [`experiments/ai-processing/results.md`](../experiments/ai-processing/results.md) §(a); the list of supported and unsupported schema features
  is DOCUMENTED in Anthropic's API documentation (cached 2026-10).
- Implication: there are three validation layers. First the API schema. Then Pydantic constraints. Then semantic checks:
  Hangul ratio, verbatim entity grounding, language match, numbers preserved. A failure is retried **once**, then sent to
  the review queue. It is never mass-retried.

### F-G-02 · Route by task: Haiku for bulk, Sonnet for briefings
| Per item (TESTED, effort=low) | Haiku 5.5 | Sonnet 5.5 | Ratio |
|---|---|---|---|
| Extraction + KO summary (≈4.5k in / 1.7–1.9k out tokens) | $0.0013, 8.6 s median | $0.0275, 13.2 s | ≈21× |
| Triage (title + lead, ≈2.3k in / 150 out) | $0.0003, 1.8 s | $0.0062, 2.6 s | ≈21× |
- Quality: both were 100% schema-valid with v2 and 98% vs 100% grounded. On the full read Sonnet was richer (context,
  record-framing) and Haiku correct but thinner. The two models' triage scores differed by 7.8 points on average, agreeing
  at the top and bottom. Prices are from Anthropic's model table (DOCUMENTED, cached 2026-10-06: Haiku 5.5 $0.10/$0.50,
  Sonnet 5.5 $2/$10 per MTok). **Re-check the live pricing page before budgeting.**
- Anthropic's guidance also recommends measuring "the larger model at lower effort" before building a cascade. Here Sonnet at
  `low` was still about 21× Haiku per item, so the cascade wins for bulk work.

### Cost at MVP volume (INFERRED from TESTED unit costs; R6 will measure the real rate)
| Line | Assumption | Per day |
|---|---|---|
| Triage, every new item after dedup | 1,000–3,000 × $0.0003 | $0.30–0.90 |
| Enrichment for items at "review" band or above | 40% × 1,000–3,000 × $0.0013 | $0.52–1.56 |
| Enrichment for every item (if wanted) | 1,000–3,000 × $0.0013 | $1.30–3.90 |
| Briefings (Sonnet), 2 editions | ~30 items × ~600 tokens in, ~3k out, with thinking | ≈ $0.10–0.30 |
| Natural-language search answers | 50 queries × Haiku ≈ $0.001, or Sonnet ≈ $0.02 | $0.05–1.00 |
| **Total** | | **≈ $1–5 a day (≈ $30–150 a month)** |
| Counterfactual: Sonnet for all enrichment | 3,000 × $0.0275 | ≈ $82 a day |

The Batch API (asynchronous, 50% off, results keyed by `custom_id` in any order; DOCUMENTED in Anthropic's API documentation) suits archive
backfill and overnight re-enrichment, not the live desk path.

### Other patterns
- **Prompt design for untrusted input:** a fixed system prompt (data-not-instructions rule, canary, attribution rule);
  the article wrapped in `<article>` with `</article>` neutralised; trusted metadata (URL, publication date, source ID)
  placed outside the article block; an `injection_suspected` and `injection_note` field. TESTED: the hardened prompt
  removed the payload echo from the summary (Sonnet naive 2/6 → 0/6).
- **Caching keyed by content:** the cache key is `sha256(model, prompt_version, schema_version, text_sha256)`. A re-run
  or a duplicate item costs nothing. TESTED: the experiment re-ran from its cache. Anthropic **prompt caching** does not
  help yet, because the ~300-token system prompt is below the minimum cacheable prefix (512–4,096 tokens, depending on the
  model; DOCUMENTED). Revisit if the desk profile or few-shot examples grow.
- **Retries and timeouts:** the SDK retries 408/409/429/5xx and connection errors (default 2; set 3) with a per-request
  timeout of 60–180 s. Validation failures are deterministic: retry once at most, then route to review. Always check
  `stop_reason` (`refusal`, `max_tokens`) before parsing. Haiku 5.5 has **no server-side refusal fallback**. Sonnet 5.5
  supports `fallbacks: "default"` (beta) on the Claude API (DOCUMENTED). Refusals observed: 0/142 on war, death
  and violence content (TESTED).
- **Idempotency:** one output row per (article, task, prompt_version, schema_version). Workers write their own row and
  never append to a shared file.
- **Human review queue triggers:** a validation failure after the retry, `injection_suspected` true (or the regex
  pre-filter hit), an ungrounded entity, a "flash" band, a detected conflict, and every briefing before it is sent.
- **Audit trail (AI output kept separate from source):** `articles` (immutable text plus `text_sha256`) and
  `ai_outputs(article_id, task, model, prompt_version, schema_version, input_sha256, output_json, validation_status,
  flags, cost_usd, latency_ms, created_at)`, plus `reviews(ai_output_id, reviewer, decision, edited_json, at)`. The UI
  labels AI text and links to the source sentence.

## 3. Translation options (question 3)

| Option | KO↔EN / ZH→KO evidence | Cost | Terms | Tag |
|---|---|---|---|---|
| **Claude (Haiku 5.5 in the enrichment call)** | Korean summaries from EN, ZH and KO were correct on a full read; transliterations correct; translation shares the extraction call | ≈ $0.0013 an article including summary and extraction | Anthropic commercial terms; API data is not used for training by default (not re-checked in this round) | TESTED (summary); full-text translation INFERRED |
| DeepL API | Supports KO and ZH per its language list (not re-checked) | Third-party guides report $25 per 1M characters (≈ $0.11 for a 4.5k-character article) and a 2026 plan restructure (Free/Pro closed to new signups, "Growth" plan). The official page fetched did not show API prices | The Pro FAQ says texts are "never used to train" and stored temporarily | UNVERIFIED (price); DOCUMENTED (training statement, https://www.deepl.com/en/pro-api) |
| Papago (Naver Cloud) | Strong reputation for KO; no measured evidence gathered | Billed per 1M characters; **the rate is not on the public page** (console only); a third-party figure was unverifiable | Naver Cloud terms | DOCUMENTED (billing unit, https://www.ncloud.com/product/aiService/papagoTranslation); price UNVERIFIED |
| Google Cloud Translation | Gemini 2.5 Pro led the preliminary automatic WMT25 rankings; anonymised commercial MT systems ranked mid-table | Snippets of the official page: Translation LLM $10 per M in + $10 per M out; Adaptive $25 per M; NMT ≈ $20 per M; $10 monthly credit. The page fetch returned no body | Google Cloud terms | DOCUMENTED (search snippets of https://cloud.google.com/translate/pricing); not re-read |
| WMT25 human evaluation (EN→KO newly added, MQM-scored) | Final per-system EN→KO tables **not retrieved** | — | — | UNVERIFIED; leads: https://aclanthology.org/2025.wmt-1.1 and https://arxiv.org/abs/2508.14909 |

**Verdict (INFERRED):** the MVP needs no dedicated MT API. Translation for desk understanding happens inside the
enrichment call at roughly 1/80th of DeepL's reported per-character price. A dedicated MT engine earns a place only as a
**second opinion on verbatim quotes that will air**. Decide between DeepL and Papago in round 2 with a blind native-speaker
test on 30 quotes. That test is **BLOCKED-no-key** (no DeepL, Papago or Google keys).

## 4. Local versus hosted, and the degradation path (question 4)

- **Local inference is excluded by project policy.** Hosted only. Primary: Anthropic (key present, TESTED). Embeddings,
  if ever needed: OpenAI (key present). ASR: Groq Whisper (R8).
- **Portability layer:** the provider contract is *JSON Schema plus a local validator*, not a vendor SDK feature. A second
  hosted LLM could be swapped in behind the same schema and validator, though none is needed for the MVP.
- **When the provider is down (429/5xx/timeout) or refuses:**

| Function | With AI | Without AI (degraded mode) |
|---|---|---|
| Collection, normalisation, dedup, clustering | Unchanged | Unchanged (deterministic) |
| Search | BM25 + LLM query rewrite + answer | BM25 + filters; the user types KO/EN terms |
| Alerts | Rules + relevance bands | **Rules only** (watchlist, source priority, event size); the LLM score is shown as "pending" |
| Desk queue | Korean headline and summary | Original title and lead plus the source language tag, "AI 처리 대기" |
| Briefing | Sonnet draft with citations | Template: top clusters by source count and recency with original titles |
| Feed health | Unchanged | Unchanged |

  Each item carries `enrichment_status` (pending, done, failed, review). A worker drains the queue with exponential
  backoff and a per-day $ cap. After a long outage, items older than N hours go through the Batch API.

## 5. RAG and natural-language search (question 5)

**Verdict: not needed for the MVP (INFERRED).** The archive is news with strong lexical signals (names, places, dates),
and desk queries are mostly entity-plus-time. The hard part is **cross-lingual recall** ("김여정" against "Kim Yo
Jong" against "金與正"). It is solved more cheaply by (a) the extraction call storing `name_original` and `name_ko`, so
the index carries both forms, and (b) a Haiku query-rewrite step that expands the question into KO/EN/ZH keywords plus
filters. An LLM then answers over the top-k BM25 hits with mandatory `article_id` citations. Add embeddings (OpenAI) only
if R6 finds that dedup or clustering needs them, or if search logs show semantic misses that keyword expansion cannot fix.
pgvector against FTS5 is a D4 question for R6.

## 6. Agents and MCP (question 6)

- **No runtime agent in the MVP, and no multi-agent design.** Every MVP AI task is either a single call or a fixed
  workflow whose steps are known in advance (§1). Anthropic's own guidance applies: an agent is warranted only when
  the task is multi-step and hard to specify, its value justifies the cost, and errors are recoverable. Only "research
  assistance" passes, and it is deferred.
- **MCP:** a read-only server whose tools wrap the REST API. Schemas, auth and trust labelling are in
  [`technology/mcp-tool-design.md`](mcp-tool-design.md). Returned source text is labelled `untrusted_source_text`, AI fields
  carry model and prompt version, there are no outbound or URL-fetch tools, and write tools are opt-in under a separate
  scope. Local use runs over stdio with an environment token. Remote use runs over Streamable HTTP with OAuth 2.1 per the
  MCP authorization spec (DOCUMENTED).

## 7. AI security (question 7)

The full model is in [`technology/ai-threat-model.md`](ai-threat-model.md). TESTED results that drive it:
- 0/24 extraction hijacks (summary replaced) and 0/24 canary or system-prompt leaks across both models and both
  conditions. The tool-less design means an exfiltration attempt has no channel except text.
- 48/48 attacked calls set `injection_suspected` true. 0 false positives on 44 clean hardened calls.
- **The subtle score attack partly worked** (Haiku +22.6 mean, n=5; Sonnet +8, n=2) **despite the flag.** The control is
  deterministic: a flagged item's model score is discarded, the item is re-scored with the flagged span removed or capped,
  and it goes to human review.
- In the naive prompt Sonnet echoed the attacker's fabricated headline into the Korean summary as a quoted meta-note
  (2/6). The hardened prompt kept it in `injection_note` (0/6). Model output must be rendered as plain text, with links
  removed (the exfil URL appeared in 3/6 naive notes).
- Mandatory controls: no tools on content calls; schema plus local validation; delimiting; deterministic handling of the
  flag plus a regex pre-filter; provenance separation; plain-text rendering; human approval for any external action; a
  read-only MCP server; spend caps.

## 8. What was not established

- No gold-standard quality evaluation. Quality rests on cross-model agreement, verbatim grounding and one full read. A
  50-item desk-labelled set (relevance bands plus summary acceptability) is the round-2 offer.
- Injection tests used English, fairly obvious payloads on 3 articles. Korean and Chinese payloads, quote-embedded
  injections and attribution laundering are untested.
- The DeepL, Papago and Google translation comparison is BLOCKED-no-key. Their prices are UNVERIFIED or snippet-level.
- The Batch API, prompt caching and server-side refusal fallbacks were not exercised.
- Model prices come from a cached copy of Anthropic's model table (2026-10-06), not from the live pricing page or billing meter.
