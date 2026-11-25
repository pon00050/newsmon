# ADR-006 · Where AI is used, which provider, and how the system degrades without it (D6)

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: O1 and one O2 call (assessment) built; O3 and O4 deferred.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Informs:** FR-11…FR-15, FR-22, ADR-010 (AI provider abstraction), deliverable 11 §4.

## Context (TESTED by R7 unless marked; [`experiments/ai-processing/results.md`](../../experiments/ai-processing/results.md))

- Structured outputs: 0 JSON-parse failures and 0 refusals in 142 calls; the v1 date contract broke 2/11 (Haiku) and
  1/11 (Sonnet), v2 schema passed 14/14 (F-G-01).
- Cost per item (effort=low): Haiku 5.5 extraction $0.0013, triage $0.0003; Sonnet 5.5 $0.0275 / $0.0062 (≈21×) (F-G-02).
  Prices from a cached copy of Anthropic's model table (2026-10-06); re-check the live page before budgeting.
- Security: 0/24 hijacks in tool-less schema-constrained calls; 48/48 attacked calls flagged `injection_suspected`, 0 false
  positives on 44 clean hardened calls; **a subtle score attack moved Haiku +22.6 and Sonnet +8 while the flag was set**
  ([`technology/ai-threat-model.md`](../../technology/ai-threat-model.md) T2).
- Triage score noise ±15 on repeats (`repeat_triage_results.json`).
- Embeddings (OpenAI `text-embedding-3-small`) are needed for clustering (ADR-005).
- No local inference (project policy). Licensed wire contracts may bar sending text to a third-party model
  (`02_COMMERCIAL…` §6 consequence (d); `08_LEGAL…` §9(b) risk 6); supplement 02 asks for local-vs-external AI processing.

## Options considered

| Level (R7 §1) | Where it could apply | Verdict |
|---|---|---|
| 1 no AI | Collection, dedup, search, rules, alerts, feed health, language ID by script ratio | **Default everywhere possible** |
| 3 single LLM call | Triage band; enrichment (Korean headline + summary, translation of key quotes, who/what/where/when, entities, attributed claims, injection flag); query rewrite | **Adopt** |
| 4 fixed workflow | Briefing draft (rules select → Sonnet writes with citations → code checks citations → human approves) | **Adopt** |
| 5 agent | Research assistance | **Defer**; the user's own MCP client covers it (ADR-008) |
| RAG / vector search | Search | **Reject for MVP** (BM25 + cross-lingual entity forms + query rewrite) |
| Dedicated MT API (DeepL, Papago, Google) | Translation | **Defer** (BLOCKED-no-key; quote second-opinion only) |

## Architecture options with and without AI (project-owner guidance, 2026-11-25)

The project owner asked to "consider all options of using and not using LLM or AI agents", and noted that training is not needed.
**There is no model training or fine-tuning anywhere in this design** (DR-7 already forbids training on third-party
text). The four options below are cumulative; each is a configuration of the same codebase, not a separate build.

| | **O1 fully deterministic** | **O2 = O1 + optional single LLM calls** | **O3 = O2 + cloud embeddings** | **O4 = any of the above + an external agent via read-only MCP** |
|---|---|---|---|---|
| What runs | Rules, boolean/keyword profiles, gazetteer entity lists with KO/EN/ZH aliases, dateline regex, BM25/FTS5 bigram search, URL + hash + MinHash dedup, per-language TF-IDF incremental clustering, weighted rule ranking, rolling z-score spikes, template digests | O1 + Haiku triage band, Haiku enrichment (Korean headline/summary, key-quote translation, who/what/where/when, entities, attributed claims), Sonnet digest drafts, LLM query rewrite | O2 + `text-embedding-3-small` for event clustering | The user's own Claude Desktop/Code queries the system through read-only MCP tools; no agent runs inside the system |
| Desk coverage (responsibility rows, deliverable 09 `min_mode` column) | Collection, dedup, grouping (same-language), search, queue, registration, alerts, feed health, handoff/morning digest (titles + links), archive search | Adds the Korean understanding layer: R-05, R-06, R-10, R-17 move from "original language only" to "Korean summary"; better triage on items rules miss | Adds cross-source and cross-language event grouping quality | Adds open-ended research questions ("trace how X evolved") on the user's side |
| Measured quality (phase 1) | **Dedup:** recall 0.989–0.993 vs exact Jaccard (TESTED, identical in all modes). **Search:** KO/ZH recall 1.00 on substring truth, 0 nonsense hits (TESTED). **Clustering:** TF-IDF pair F1 0.371, B³ 0.837, **cross-lingual pair recall 0** (θ 0.15); at θ 0.2 precision 0.87, recall 0.21 (TESTED). **Relevance:** rules unmeasured (no desk gold set). **Korean summaries of English/Chinese text: none** | **Summaries:** 22/22 Korean summaries correct on a full read; entity grounding 98–100%; v2 schema 14/14 valid (TESTED, small n). **Relevance:** LLM triage noise ±15 points on repeats (35–62 over 5 runs), Haiku–Sonnet mean difference 7.8; a planted "editor's note" moved scores +22.6 (Haiku) despite the flag (TESTED) | **Clustering:** pair F1 0.776, B³ 0.901, cross-lingual pair recall 0.36 (TESTED; thresholds tuned on the scored set, so optimistic) | No measurement (T6 risk is INFERRED) |
| API cost | $0 | ≈ $1–5/day at 1,000–3,000 items (INFERRED from TESTED unit costs) | + ≈ $0.01/day for embeddings at 3,000 items (INFERRED from $0.002 per 826 items) | Paid by the user's own client; server side $0 |
| Licence compatibility | Works on every source, including `external_ai_allowed=false` wires and `ai_processing=no` sources | Only items with `ai_processing ≠ no` and (`external_ai_allowed=true` or a customer-hosted endpoint); `unknown` sends title + feed summary only | Same gate as O2 for the embedded text | **MCP returns text to the client's model, which is usually hosted.** So MCP applies the same gate: items with `external_ai_allowed=false` return metadata + headline only through MCP |
| Failure modes | Under-merging (one story split into many rows); misses paraphrase and cross-language links; monitors read English/Chinese originals; rule weights need tuning; keyword lists drift | Provider outage, spend runaway, fabrication (2/218 entities paraphrased; a v1 invented date), score manipulation by injected text, PIPA cross-border exposure (§9(d)) | Model version drift breaks stored vectors (store model id, re-embed); over-merging long sagas | The client agent follows instructions in returned article text (T6); outside the system's control; read-only tools and trust labels only reduce it |

**Where O1 is plainly weaker** (stated, not implied away):

- **No Korean summary or translation of English or Chinese text.** A Korean monitor sees the original headline, plus the
  feed snippet where `display ≥ snippet`. This is the seat's summarise/translate duty, and O1 does not perform it.
- **Cross-lingual event linking is absent.** A Yonhap story and the Guardian story on the same event stay separate events,
  unless the editor merges them or both hit the same gazetteer entity inside the window.
- **Same-language clustering under-merges.** Recall is 0.21 at the safe threshold, so the queue shows more rows per real
  event.
- **Relevance covers only what the rules name.** An important item with no watched term or entity reaches `review` only
  through source weight and independent-source count.
- **Briefings are lists of titles and links, not prose.**

**MVP stance:** the MVP is **fully functional in O1** with no AI provider configured. O2 and O3 are switched on by
configuration, per capability (`ai.capabilities.{triage, enrich, embed, digest_draft, query_rewrite}`) and per source (the
licence flags). O4 is the optional MCP server, gated as above.

## Decision

1. **Provider routing:** Anthropic `claude-haiku-5-5` for triage and enrichment, `claude-sonnet-5-5` for briefing drafts
   and on-demand analysis; OpenAI `text-embedding-3-small` for clustering. SDK pins as used in phase 1: `anthropic==2.14.0`,
   `pydantic==2.14.4` ([`experiments/ai-processing/requirements.txt`](../../experiments/ai-processing/requirements.txt)); embeddings were called over plain HTTPS
   (private experiment data (not published)), so an `openai` SDK version is not verified.
2. **Every content call is tool-less and schema-constrained** (M1, M2), with three validation layers (API schema →
   Pydantic → semantic checks: Hangul ratio, verbatim entity grounding, numbers preserved), one retry, then the review queue.
3. **Injection handling is deterministic** (M4, M5): an EN/KO/ZH regex pre-filter OR the model flag → the model's score
   is discarded, the item is banded `review`, tagged ⚠, and never auto-alerted or auto-included in a digest.
4. **Bands, not fine scores:** drop / review / report / flash; rules first (watch terms, entities, source tier, independent
   sources), LLM band second; the final band = max(rule band, LLM band) unless flagged, capped at `report` from the LLM alone
   (only rules can raise `flash`). INFERRED from the noise and attack results.
5. **AI provider abstraction** (`AIProvider` interface: `complete_json(schema, system, content) → result + usage`,
   `embed(texts) → vectors + model_id`). Endpoint kinds:
   - `anthropic_api` (hosted; MVP);
   - `openai_embeddings_api` (hosted; MVP);
   - `customer_hosted` (an HTTPS endpoint inside the customer's network, OpenAI- or Anthropic-compatible): **designed,
     not implemented or run** in the MVP. Nothing runs locally on this workstation (no-local-inference policy).
   Routing per item: if `ai_processing=no` → no call; if `external_ai_allowed=false` → only a `customer_hosted` endpoint may
   be used, else no call; otherwise the configured hosted endpoint. Provider and region are per-deployment config
   (`08_LEGAL…` §9(c), §9(d), DR-9).
6. **Caching keyed by content:** `sha256(model, prompt_version, schema_version, input_sha256)`; duplicates cost nothing.
7. **Spend guard:** per-day USD cap (default $5) and an alarm at 2× expected daily spend (M10); when the cap is hit,
   enrichment pauses and the system runs in degraded mode until the next day.
8. **Labelling:** every AI field carries `generated_by_ai=true`, model and prompt version; UI shows "AI 생성" (DR-8);
   model text is rendered as plain text with links stripped (M7).
9. **No training or fine-tuning** of any model, on any data (DR-7; project-owner guidance 2026-11-25).
10. **O1 is the baseline mode**, not a fallback afterthought. Every MVP capability has an O1 implementation, with its own
    acceptance criteria (deliverable 12 §5).

## Degradation (AI off, provider down, cap hit, or item not allowed to reach AI)

| Function | With AI | Without AI |
|---|---|---|
| Collection, normalisation, dedup, search, feed health | unchanged | unchanged |
| Clustering | embedding incremental | per-language TF-IDF (precision 0.87, recall 0.21) |
| Queue | Korean headline + summary, band | original title (+ feed summary only if `display ≥ snippet`), rule band, "AI 처리 대기" |
| Alerts | rules + bands | rules only |
| Briefing | Sonnet draft with citations | template: top events by independent sources and recency, original titles |
| Search | BM25 + LLM query rewrite | BM25 + deterministic alias expansion from the entity gazetteer |

Each article has `enrichment_status` (pending, done, failed, review, not_allowed); a worker drains `pending` with
exponential backoff when the provider returns.

## Consequences

- Expected AI spend ≈ $1–5/day at 1,000–3,000 items/day (INFERRED from TESTED unit costs, `06_AI…` §2).
- Under Model B with `external_ai_allowed=false` and no customer endpoint, licensed items run on the no-AI path (ADR-003).
- Quality is unproven against a desk gold set (R7 §8); S2's test plan owns that.

## Evidence

[`technology/ai-and-agent-integration-report.md`](../../technology/ai-and-agent-integration-report.md) §0–§7 · [`technology/ai-threat-model.md`](../../technology/ai-threat-model.md) ·
[`experiments/ai-processing/results.md`](../../experiments/ai-processing/results.md), `metrics.json`, `repeat_triage_results.json` ·
[`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) F-L-06, DR-7…DR-9, §9(c), §9(d).

## Reversal triggers

- A desk gold set shows Haiku enrichment unacceptable → route enrichment to Sonnet for `report`/`flash` items only.
- Korean/Chinese injection tests (round 2) show unflagged attacks → raise the regex layer, cap LLM influence further.
- PIPA counsel says sending names to a US-hosted LLM needs a route the tenant lacks → per-tenant entity-masked inputs or a
  Korean-region/customer-hosted endpoint (`08_LEGAL…` §9(d)).
- A customer's contract permits hosted AI processing. The customer sets `external_ai_allowed=true` and the permitted ops on
  that source (ADR-010 §4). This is configuration only; the default for unconfigured sources does not change.
