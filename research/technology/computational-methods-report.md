# 05 · Computational methods report (R6, Workstreams E + F, 2026-11-25)

> **Status: Experimental result.** Deliverable 05. Measured on small samples; see the experiments.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Decisions informed:** D4 (storage), D5 (dedup and event clustering), and the data model behind 11 and 12.
**Companion:** [`technology/data-model-and-lifecycle.md`](data-model-and-lifecycle.md) holds the ERD, DDL, lifecycle and the full
DB decision.

**Evidence:** the four experiments below, each with scripts, inputs, outputs and a RESULTS.md. API spend was about
$0.21 ([`experiments/event-clustering/cost.md`](../experiments/event-clustering/cost.md)).

## 1. Answers first

| Decision | Recommendation | Tag | Evidence |
|---|---|---|---|
| **D4 storage** | **SQLite (WAL) + FTS5 + optional sqlite-vec** for the MVP. Migrate to PostgreSQL + pgvector when the triggers in the companion doc §5 fire: concurrent writers, more than 10 M revisions, multi-tenant clients, or archive-wide vector search. | TESTED (FTS) + INFERRED (scale) | [`experiments/korean-fts/results.md`](../experiments/korean-fts/results.md) |
| **D4 KO/ZH search** | FTS5 is adequate **only with the right tokenizer**: `trigram` with `LIKE` for queries under 3 characters, or CJK bigram pre-tokenisation. Both had recall 1.00 on KO and ZH. Plain `unicode61` had recall 0.68 on KO and **0.09 on ZH**. `trigram` MATCH returns **0 rows for 2-character queries** such as 북한, 미국 and 中国. | TESTED | same |
| **D5 dedup** | Exact canonical URL plus content SHA-256, then **MinHash-LSH** (128 perms, char 4-grams): t = 0.9 collapses, t = 0.5 links as syndicated or revised. SimHash is not needed: it recovers only 45% of J ≥ 0.5 pairs on short text. | TESTED | [`experiments/deduplication/results.md`](../experiments/deduplication/results.md) |
| **D5 source independence** | Count sources by **registrable domain (eTLD+1)**, and corroboration by **distinct near-duplicate clusters**. In the test, 75 GDELT hosts were 31 domains, 44 of them iHeart stations carrying one story. | TESTED | same |
| **D5 event clustering** | **Cloud embeddings (`text-embedding-3-small`) + time-windowed incremental single-pass clustering**, with a lower cross-language threshold: θs ≈ 0.55–0.6, θx ≈ 0.45, 48 h window. Pair F1 0.78 and B³ 0.90, against TF-IDF at 0.37 / 0.84. **Cross-lingual linking stays weak** (36% of cross-lingual pairs). Round 2 should test translate-then-embed, or LLM confirmation of 0.35–0.5 candidates. | TESTED (LLM-assisted gold) | [`experiments/event-clustering/results.md`](../experiments/event-clustering/results.md) |
| **Fallback without AI** | Per-language TF-IDF incremental clustering at θ = 0.2 gives pair precision 0.87 and recall 0.21. That is safe but under-merges. Dedup and search do not depend on AI at all. | TESTED | same |
| **Volume and spikes** | A rolling z-score (trailing 7 points, z ≥ 2.5) flagged the obvious peak. CUSUM missed it. GDELT timelines have gaps (23 of 30 days present) and shared-IP rate limits. Use the system's own per-event counts as the primary signal. | TESTED (n = 1 series) | [`experiments/event-clustering/spike-detection/results.md`](../experiments/event-clustering/spike-detection/results.md) |

## 2. Experiment results (summary; see each RESULTS.md for the full tables and limits)

### 2.1 Corpus
- **Rows:** 971 in total, from 23 publisher RSS feeds discovered on the publishers' own pages (EN 224, KO 482,
  ZH 190) plus 75 GDELT DOC rows.
- **Rate:** 571 unique items in 24 h, about 25 per feed per day.
- **GDELT:** only 1 of 9 artlist calls succeeded, because of a shared-IP rate limit.
- **No feed found** (UNVERIFIED-absent, after one page check each): BBC, DW, Yonhap EN, 한겨레, KBS, 联合早报, UN News.

### 2.2 Dedup (919 unique-URL docs, title + summary)

| Method | Recall vs exact Jaccard | Precision vs exact | Note |
|---|---|---|---|
| MinHash-LSH t = 0.5 | 0.989 | 0.956 | Catches Yonhap→SBS rewrites (J 0.54–0.63) |
| MinHash-LSH t = 0.9 | 0.993 | 0.998 | |
| SimHash Hamming ≤ 3, J ≥ 0.9 | 0.991 | 0.998 | |
| SimHash Hamming ≤ 10, J ≥ 0.5 | **0.449** | 1.000 | Too coarse for rewrites |

- **Hand-checked:** 31 of 32 sampled pairs at J ≥ 0.3 were the same story. The sample is skewed toward iHeart pairs.
- **Known false positives:** Guardian live-blog boilerplate (J 0.63) and a Yonhap "[북한단신]" pair (J 0.38).
- **Canonicalisation:** courlan merged 0 URLs on publisher RSS. Two cases of the same content under different URLs
  were caught only by the content hash.

### 2.3 Event clustering

**Gold set:**
- 240 items, 80 per language, labelled in one call by Claude Sonnet 5.5.
- **The gold set is LLM-assisted:** about 120 of 240 labels were checked by an AI research agent, and 1 was corrected.
- It has 158 events and 327 same-event pairs, 125 of them cross-lingual.
- One 19-item event holds 171 of the pairs.

| Method | Best setting | Pair F1 | B³ F1 | Cross-lingual pair recall | Time (240 items) |
|---|---|---|---|---|---|
| TF-IDF incremental, per language | θ = 0.15 | 0.371 | 0.837 | 0 | 2.7 s |
| Embedding incremental, one threshold | θ = 0.5 | 0.721 | 0.878 | 0.22 | 0.16 s |
| **Embedding incremental, θs 0.55 / θx 0.45** | | **0.776** | **0.901** | 0.36 | <0.2 s |
| Agglomerative (average linkage) | d = 0.5 | 0.743 | 0.885 | 0.21 | 0.01 s |
| HDBSCAN | mcs = 3 | 0.408 | 0.806 | 0.26 | 0.02 s |

**Cosine similarity of same-event pairs:**
- same-language: median 0.67;
- **cross-language: median 0.41**, which overlaps the most similar unrelated cross-language pairs (median 0.37).

Thresholds were tuned on the same gold set they are scored on, so the numbers are optimistic.

### 2.4 KO/ZH FTS5
See §1. The nonsense controls returned 0 hits for every method, so a null result from these methods is a real null.

### 2.5 Spikes
On the GDELT "Ukraine" series:
- z ≥ 2.5 flagged 11-14 and 11-19 (11-19 is the maximum, at 1.7× the trailing mean);
- CUSUM flagged only the sustained rise on 11-16.

## 3. Algorithm selection matrix

**Tag key:**
- T = TESTED here.
- D = DOCUMENTED by the maintainer or vendor.
- I = INFERRED.
- U = UNVERIFIED.

All rows are dated 2026-11-25. Complexity is given as n = items and k = live clusters.

| # | Problem | Candidate methods | Inputs → outputs | Complexity | Advantages | Failure modes | Evaluation | **Recommended MVP approach** | Tag |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Exact duplicates | Canonical URL key (courlan + rules); SHA-256 of normalised text; GUID | URL, text → dup flag | O(1) per item | Deterministic and free | Same content under 2 URLs (seen at France24); tracking params from social links | Count merges, check by hand | URL key **and** content hash, both | T |
| 2 | Near-duplicates and syndication | MinHash-LSH; SimHash; all-pairs Jaccard (small n); embedding cosine | Char 4-gram shingles → pairs with Jaccard | MinHash ~O(n); exact O(n²) | MinHash is tunable to the rewrite range | Boilerplate and live blogs give false positives; KO rewrites sit at J≈0.55 | Recall vs exact Jaccard; hand-checked precision | MinHash-LSH 128p, t 0.9 collapse / t 0.5 link, with per-source boilerplate stripping | T |
| 3 | Text similarity (same language) | TF-IDF cosine; BM25; embeddings | Text → score | O(d) per pair | TF-IDF is free and explainable | Lexical methods miss paraphrase (TF-IDF clustering recall 0.2) | Same-event pair recall | Embeddings for clustering; BM25 for search | T |
| 4 | Embeddings | OpenAI text-embedding-3-small/large; Voyage, Cohere multilingual (cloud only; no local models by policy) | Text → 1,536-d vector | 1 API call per 200 items | $0.002 for 826 items, 0.4 s per batch | API outage; model version drift breaks stored vectors | Clustering F1 | 3-small; store the model id with every vector, re-embed on a model change | T (3-small), U (others) |
| 5 | Multilingual / cross-lingual similarity | Raw multilingual embeddings; translate-then-embed (LLM or MT); entity-anchored linking; LLM pair confirmation | KO/ZH/EN text → cross-lingual link | +1 LLM call per item (translate) or per candidate pair | Translation also feeds the desk's summaries | Raw embeddings: same-event 0.41 vs unrelated 0.37, heavy overlap | Cross-lingual pair recall on gold | Separate θx 0.45 now (recall 0.36); **round-2 test** of headline translation to EN before embedding | T (raw), I (fixes) |
| 6 | Event clustering | Incremental single-pass with time window; agglomerative; HDBSCAN; TDT-style story chaining | Vectors, timestamps → event ids | O(n·k) streaming | Streaming, explainable, cheap | Over-merging long sagas (the Huang story); thresholds drift by language | Pairwise and B³ F1 on gold | Incremental, θs 0.55–0.6, θx 0.45, 48 h; nightly agglomerative re-check optional | T |
| 7 | Topic classification | IPTC Media Topics taxonomy (https://iptc.org/standards/media-topics/, a hierarchical news taxonomy; not fetched this round); LLM zero-shot onto top levels; keyword rules; supervised classifier later | Text → IPTC code(s) | 1 LLM call per item, or batch | Standard vocabulary shared by agencies | LLM label drift; deep taxonomy levels unreliable | Agreement against an editor sample | LLM to IPTC top level plus one sub-level, stored in `ai_interpretation`; keyword rules as fallback | U (taxonomy), I |
| 8 | NER and entity resolution | LLM extraction; cloud NER APIs; gazetteer of desk-relevant names (KO/ZH/EN aliases) + Wikidata QIDs | Text → mentions → entity ids | 1 LLM call per item; gazetteer O(text) | Gazetteer is deterministic and multilingual via aliases (陳吉寧 / 陈吉宁 / 천지닝) | Transliteration variants; traditional vs simplified Chinese | Precision and recall on a hand sample | Gazetteer for watch-list entities + LLM NER for the open set, resolved to QIDs | I |
| 9 | Temporal event detection (new event) | First item of a new cluster (incremental); burst detection per entity | Cluster stream → "new event" flag | O(1) | Comes free from #6 | Re-surfacing old stories looks new | Time-to-detect against wire timestamps | New cluster plus count ≥ 2 independent sources within N hours | I |
| 10 | Geographic extraction | Gazetteer (GeoNames) matching; LLM extraction; dateline parsing ("(카이로=연합뉴스)", "（中央社台北24日電）") | Text → place, country codes | O(text) | Datelines are highly reliable in wire copy | Ambiguous names; dateline is not the event place | Hand sample | Dateline regex per source + LLM country tags | I (dateline pattern seen in corpus) |
| 11 | Novelty (new information in an ongoing event) | Max similarity to earlier cluster members; LLM "what's new" diff | Item + cluster → novelty score | O(cluster size) | Cheap with embeddings | Paraphrase scores as novel | Editor judgement | 1 − max cosine to earlier members, with an LLM diff only for desk-flagged events | I |
| 12 | Anomaly and volume spikes | Rolling z-score; CUSUM; seasonal (STL) baselines | Counts per time bucket → spike flags | O(n) | Simple and explainable | Gaps read as drops; low counts give noise | Flags against known peaks | Rolling z ≥ 2.5 on per-event and per-entity counts, with a minimum-count floor; own counts first, GDELT as context | T (n = 1) |
| 13 | Source independence and syndication | eTLD+1 grouping; owner-group table; near-dup clusters; wire-attribution regex ("(AP)", "연합뉴스", "Reuters") | Sources, near-dup links → independent-source count | O(n) | Prevents "44 confirmations" from one wire story | Ownership not visible in the domain | Hand audit of high-count events | Independent sources = distinct eTLD+1 ∩ distinct near-dup clusters; maintain `owner_group` | T |
| 14 | Relevance ranking | BM25 (FTS5 `bm25()`); weighted rules (source tier, watch-list entity, recency, cluster size, independent sources); learning-to-rank later | Query or profile → ranked list | O(log n) | Explainable to the desk | Rule weights need tuning | nDCG on an editor-labelled sample | BM25 + weighted rules, weights in config | I (BM25 is D: https://www.sqlite.org/fts5.html) |
| 15 | Newsworthiness | Rules (independent-source count, velocity, wire flash, watch-list hit); LLM rating with a rubric | Event → score + reason | 1 LLM call per event | Rules are transparent; LLM catches nuance | LLM over-rates sensational items | Agreement with desk "report" decisions | Rules first; LLM rubric score as a second opinion, stored separately from the editorial verdict | I |
| 16 | Contradiction detection | LLM NLI over claim pairs within an event; numeric-claim comparison (casualty counts) | Claims → contradicts / supports | O(claims²) per event, so cap it | Valuable to the desk (casualty figures) | Hallucinated contradictions; translation nuance | Hand-checked sample | Defer to post-MVP; MVP does only a numeric-field diff (casualties, amounts) within an event | I |
| 17 | Timeline construction | Order cluster members by published time, collapse revisions and near-dups; LLM summarise per step | Event members → ordered timeline | O(m log m) | Falls out of the data model | Publisher timestamps missing or late (50 of 971 had no date) | Editor review | first_seen_utc as the fallback time; revisions are collapsed through `story_key` | T (missing dates), I |

## 4. Out-of-scope observations (for other agents; not acted on)
- **R5 (sources):**
  - Yonhap English `/rss` returns 400.
  - 한겨레 `/arti/RSS/` returns 404.
  - KBS news is JS-rendered (783-byte homepage).
  - GDELT DOC rate limits are shared across agents on this IP, so serialise GDELT clients.
  - CNA Taiwan feeds are served through `feeds.feedburner.com`.
- **R7 (AI):**
  - The installed `anthropic` SDK in a long-path venv failed to import because of Windows MAX_PATH, so use short venv
    paths.
  - LLM gold labelling of 240 items in one Sonnet 5.5 call took about 30k input tokens and cost about $0.21.
- **S1 (architecture):**
  - Revisions under new URLs (Yonhap "(종합)") need a `story_key`.
  - Live blogs need special handling: they mutate continuously and create near-dup false positives.
