# Optional AI enrichment


Off by default. Everything above works identically with it off, failing, over budget or paused.

**What it adds.** For selected articles, one structured call to a hosted model (default `claude-haiku-5-5`, the model chosen in the
AI-processing experiment, see `research/experiments/`) returns together: an AI relevance band (`drop` / `review` / `report`, never `flash`), editorial importance, topics,
relevance to the profile's configured targets, a short Korean rationale, and — only where the source's licence permits
the op — a Korean headline (`translate`) and a Korean summary (`summarise`). The final band is the higher of the rule
band and the AI band (capped at `report`); the AI never lowers or hides an item. AI text is shown in a separate box
labelled "AI 생성 · model · prompt version", as plain text with links and markup stripped.

**Turn it on.**
1. `settings.yaml`: `ai.capabilities.enrich: true` (optionally `ai.enrich_model`, `ai.daily_cap_usd`, `ai.selection`).
2. Put `ANTHROPIC_API_KEY` in the environment or `<config>/.env` (never in a YAML file; the loader refuses it).
3. Make sure the sources you want assessed explicitly permit it in `sources.yaml`: `external_ai_allowed: true`,
   `ai_processing` not `no`, and `permitted_ops` containing `classify` (plus `translate` / `summarise` for Korean text).
   Public feeds ship with `permitted_ops: []`, so nothing of theirs is sent until an operator decides otherwise.
   Flags are snapshotted on each article at ingest: a change applies to articles collected afterwards.
4. Edit the profile's `ai:` section (desk instructions, relevance targets, preferred topic labels).

**Which articles.** Never all of them: pending, non-duplicate articles whose rule band is at least `ai.selection.min_band`
(default `review`), optionally only from `ai.selection.sources`, at most `ai.selection.max_items_per_cycle` per cycle.
Any article can be sent by hand with the "AI 분석" button on its page or `newsmon enrich --uid <uid>`. Items filtered
out by keywords stay in the database and in the queue under the "제외" band. A withdrawn item, and any item carrying a
restriction (a wire restriction line, `withheld` status, a future embargo), is never sent, by any route.

**After a profile edit.** Existing assessments are kept and nothing is re-sent automatically. The AI page shows how
many assessments were made for an earlier profile, model, prompt or schema; `newsmon enrich --stale --limit N`
reassesses up to N of them, under the same daily cap. `newsmon enrich --stale` with AI off only prints the count.

**Controls.** The AI page (`/ai`, or click the header badge) shows status, today's spend against the cap, cumulative
tokens and cost, and items needing review, and pauses/resumes enrichment (persisted). `newsmon enrich` runs a batch now.
Unchanged content is never re-sent (cache keyed by model, prompt, schema and the exact input). Results that fail
validation (schema, Korean-language check, numbers not in the source) get one retry, then land in review. Provider
outages back off and leave items pending; the daily cap stops calls until midnight KST. Every call records the fields
sent, tokens, cost and latency in `ai_interpretation`. Header: "AI: 꺼짐" (off), "AI: 중단" (failing or capped),
"AI: 켜짐" (on).

**Safety.** Article text is untrusted data inside `<article>` delimiters with the hardened system prompt from the AI-processing experiment; no tools are
ever attached; output is schema-constrained and validated; a deterministic injection pre-filter (EN/KO/ZH) runs in every
mode and forces flagged items to `review` with a ⚠ tag.

Measured cost during development: about $0.0003 per assessed item (nine live calls, from a price table rather than a billing meter).
The public website never uses AI.
