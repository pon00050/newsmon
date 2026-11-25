# ADR-005 · Deduplication and event clustering (D5)

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: URL, content-hash and MinHash dedup built; event clustering deferred.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Informs:** FR-07…FR-10, deliverable 11 pipeline stages 5–6.

## Context (all TESTED by R6 unless marked)

- On 919 unique-URL docs, MinHash-LSH (128 perms, char 4-grams) reached recall 0.989/0.993 at t = 0.5/0.9 against exact
  Jaccard; SimHash at Hamming ≤ 10 recovered only 0.449 of J ≥ 0.5 pairs ([`experiments/deduplication/results.md`](../../experiments/deduplication/results.md)).
- courlan merged 0 URLs on publisher RSS; two same-content/different-URL cases were caught only by content hash.
- False positives: Guardian live-blog boilerplate (J 0.63), Yonhap "[북한단신]" shared lead (J 0.38).
- Source independence: 75 GDELT hosts = 31 registrable domains; 44 were iHeart stations carrying one story.
- Event clustering on a 240-item LLM-assisted gold set ([`experiments/event-clustering/results.md`](../../experiments/event-clustering/results.md)): embedding incremental
  θs 0.55 / θx 0.45 → pair F1 0.776, B³ 0.901, cross-lingual pair recall 0.36; TF-IDF per language θ 0.15 → F1 0.371;
  HDBSCAN F1 0.408. Thresholds were tuned on the scored set (optimistic). Cross-lingual same-event cosine median 0.41 vs
  unrelated 0.37.
- AI-off fallback: TF-IDF per language θ 0.2 → precision 0.87, recall 0.21.
- Spikes: rolling z ≥ 2.5 over trailing 7 points flagged the peak; CUSUM missed it (n = 1 series,
  [`experiments/event-clustering/spike-detection/results.md`](../../experiments/event-clustering/spike-detection/results.md)).

## Options considered

Exact: GUID, canonical URL, content hash. Near-dup: MinHash-LSH, SimHash, embedding cosine. Clustering: TF-IDF incremental,
embedding incremental, agglomerative, HDBSCAN, LLM-only merge (Horizon). Spikes: z-score, CUSUM, STL.

R7 recommended "no vector store; embeddings only if R6 needs them" (`06_AI…` §0 point 4). R6's experiment shows clustering
does need them (F1 0.78 vs 0.37). **Resolution:** embeddings are adopted **for clustering only**, not for RAG or search,
and they fall under the same `ai_processing` flag and provider configuration as LLM calls.

## Decision

| Stage | Method | Parameters (initial, to re-tune on a desk gold set) |
|---|---|---|
| Exact dedup | GUID when present, else canonical URL (courlan 1.5.0 + fragment strip), **and** SHA-256 of normalised title+summary+body | — |
| Near-dup | datasketch 2.0.0 MinHash-LSH, 128 perms, char 4-grams, after per-source boilerplate stripping (regex list in the source registry) | t ≥ 0.9 `same_item`; t ≥ 0.5 `syndicated` (different source) or `revision` (same source within 48 h) |
| Live blogs | URL/title patterns per source (`live`, "as it happened", "속보 종합") mark an article `is_live=1`; live items are excluded from near-dup linking and are re-fetched as revisions | — |
| Revisions under new URLs | `story_key` from source-specific rules (Yonhap "(종합)" suffix stripping) | — |
| Source independence | distinct registrable domain (tldextract 5.4.0 with its bundled suffix list) ∩ distinct near-dup clusters; `owner_group` column for known families | — |
| Event clustering | OpenAI `text-embedding-3-small` on title + feed summary (+ AI Korean headline when present); incremental single pass over open events | θs 0.55–0.6 same-language, θx 0.45 cross-language, 48 h window; model id stored with each vector |
| AI-off / `ai_processing=no` | per-language TF-IDF incremental (scikit-learn 1.9.1) | θ 0.2 |
| Re-embed | backlog drains when the provider returns; event membership is recomputed for items that entered via fallback | — |
| Spike detection | rolling z ≥ 2.5 over trailing 7 buckets on the system's **own** per-event and per-watch-term counts, with a minimum-count floor; GDELT as context only | bucket = 1 h (INFERRED; tune) |
| New-event flag | first item of a new cluster plus ≥ 2 independent sources within N hours | N = 6 (INFERRED) |

Not adopted: SimHash (too coarse for rewrites), HDBSCAN (F1 0.41), LLM-only merging (cost, injection exposure), CUSUM.
Contradiction detection is deferred (R6 matrix row 16; R7 level-4 workflow).

## Consequences

- Dedup and search never depend on AI; clustering degrades to under-merging, which is safe (precision 0.87).
- Cross-lingual linking stays weak (36% of pairs). The UI lets an editor merge or split events (`event_member.added_by =
  'editor:<user>'`).
- Every derived row stores its algorithm id (`minhash128-char4-v1`, `incr-embed3s-ts0.55-tx0.45-w48h-v1`) so it can be
  recomputed.

## Evidence

[`experiments/deduplication/results.md`](../../experiments/deduplication/results.md), `dedup_results.json`, `syndication_breakdown.json` ·
[`experiments/event-clustering/results.md`](../../experiments/event-clustering/results.md), `results/clustering_results.json`, `results/clustering_variants.json` ·
[`experiments/event-clustering/spike-detection/results.md`](../../experiments/event-clustering/spike-detection/results.md) · [`technology/computational-methods-report.md`](../../technology/computational-methods-report.md) §1–§3 ·
[`technology/data-model-and-lifecycle.md`](../../technology/data-model-and-lifecycle.md) §4.

## Reversal triggers

- A desk-labelled gold set (round 2) gives pair F1 < 0.6 at the chosen thresholds → re-tune or test translate-then-embed.
- Round-2 test of headline translation to English before embedding raises cross-lingual recall materially → adopt it.
- Embedding cost or PIPA cross-border constraints (`08_LEGAL…` §9(d)) rule out sending text to OpenAI for a tenant →
  TF-IDF fallback for that tenant, or another provider behind the same interface.
