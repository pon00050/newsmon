# Corpus and Experiment 2: event clustering (R6, 2026-11-25)

> **Status: Experimental result.** 240 items with LLM-assisted gold labels (about half spot-checked). Treat as indicative.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

All findings are TESTED unless they are tagged otherwise. Experiment 4 (spikes) is in `spike_detection/RESULTS.md`.

## Corpus (`corpus/`, private research only, do not republish)

### Feeds
- **Discovery** (`discover_feeds.py`, `corpus/feed_discovery.json`): every feed was taken from the publisher's own page,
  either its RSS index page or the `<link rel=alternate>` on a section page. robots.txt was checked first.
- **Feeds used:** 23 feeds from 12 publishers (`collect_corpus.py`, `corpus/feed_stats.json`). All 23 returned HTTP 200.
  - EN: Guardian World, Al Jazeera, France24 ×4, CNA ×2.
  - KO: Yonhap ×3, Donga, Kyunghyang, SBS ×2.
  - ZH: VOA Chinese ×3, RFI Chinese, Chinanews ×2, CNA Taiwan ×2.

### Publishers where no feed was found (UNVERIFIED-absent)
These are not claims that no feed exists. The check was one homepage or section page, scanned for
`rel=alternate`, `rss`, `.xml` or `feed` links.

| Publisher | What happened |
|---|---|
| BBC World, BBC 中文 | The pages link only to an editorial-guidelines page. `feeds.bbci.co.uk` was not used, because it would have been a guessed URL. |
| DW EN, DW 中文 | No feed link on the homepage |
| Yonhap English | `/rss` returns 400 |
| 한겨레 | `/arti/RSS/` returns 404, and no feed link on the international page |
| KBS | The homepage returned 783 bytes, so it is JS-rendered |
| 联合早报 | No feed link on the homepage |
| UN News EN/ZH | 403 |
| NPR | Timeout |

### GDELT DOC 2.0
- Only **1 of 9 artlist calls succeeded**: "Huawei Iran", sourcelang English, 75 rows. The others returned "Please
  limit requests to one every 5 seconds", even at 6–15 s spacing.
- A retry run (`gdelt_topup.py`) then hit a connect timeout. Other parallel agents share this IP, so GDELT's limit is
  effectively shared. **In production, GDELT needs one serialised client per IP.**

### Rows and rate
- **Rows:** 971 in total: RSS EN 224, KO 482, ZH 190, plus GDELT EN 75.
- **Distinct URLs:** 920. **After near-duplicate collapse** (J ≥ 0.9) and dropping the 50 rows with no date: 826.
- **Rate:** the 23 feeds yielded **571 unique items in the last 24 h** (618 in 48 h), about 25 items per feed per day.
- **Full text:** 60 pages fetched with trafilatura (`fetch_fulltext.py`, robots.txt checked per host, 0 blocked), 57
  of them with 300 or more characters.

## Gold set
- **Selection:** 240 items, 80 per language, drawn at random (seed 2026) from items published in the 48 h before
  collection (`gold/gold_items.json`).
- **Labels are LLM-assisted.** `claude-sonnet-5-5` proposed event labels in **one call over all 240 items**, so the IDs
  are globally consistent (`gold/gold_labels_llm.json`). The prompt defines an event as a specific happening, not a
  topic, and says follow-ups within about 2 days share the label.
- **Spot-check:** an AI research agent read the titles of all 108 items in the 27 multi-item events, read the summaries of
  6 borderline items, and scanned the singletons for missed entity matches. That is **about 120 of 240 labels checked;
  1 correction** (`gold/gold_label_corrections.json`): g226 "NATO AWACS to Poland" and g227 "Russian drone violated Polish
  airspace" were merged.
- **Resulting gold:** 158 events, 28 of them with more than one item, giving 327 same-event pairs. **125 of those
  pairs are cross-lingual.**
- **Known biases:**
  - The Huawei-verdict event has 19 items and holds **171 of the 327 pairs**. Pairwise metrics are dominated by it, so
    results are also reported without it.
  - The Jensen Huang saga was split into 6 sub-events by the labeller. That is a granularity judgement which lowers
    every method's recall.

## Methods (`cluster_experiment.py`, `cluster_variants.py`; outputs in `results/`)
- **(a) TF-IDF + cosine, incremental single-pass, per language.**
  - Items are taken in publish order. Each joins the most similar live cluster (last update within 48 h) if the cosine
    to the centroid is at or above θ; otherwise it starts a new cluster.
  - EN uses word 1–2-grams. KO/ZH use `char_wb` 2–3-grams.
  - IDF is fitted on the whole corpus for each language.
- **(b) OpenAI `text-embedding-3-small`**, the same incremental algorithm, cross-lingual.
  - (b2) is the same, restricted to the same language.
  - (b3) uses separate thresholds for same-language (θs) and cross-language (θx) matches.
- **(c) Batch comparators** on the same embeddings: agglomerative clustering (average linkage, cosine distance
  threshold) and HDBSCAN (`min_cluster_size` 2 and 3).

## Results (best setting of each sweep; full sweeps are in `results/clustering_results.json` and `results/clustering_variants.json`)

| Method | Setting | Pair P | Pair R | Pair F1 | B³ F1 | Cross-lingual pair recall | Time (240 items) |
|---|---|---|---|---|---|---|---|
| Baseline: all singletons | — | — | 0 | 0 | 0.794 | 0 | — |
| (a) TF-IDF incremental, per language | θ = 0.15 | 0.692 | 0.254 | 0.371 | 0.837 | 0 (cannot link) | 2.7 s (incl. IDF fit on 826) |
| (a) | θ = 0.2 | 0.872 | 0.208 | 0.336 | 0.838 | 0 | |
| (b) Embeddings incremental, cross-lingual | θ = 0.5 | 0.768 | 0.679 | 0.721 | 0.878 | 0.224 | 0.16 s |
| (b) | θ = 0.6 | 0.936 | 0.581 | 0.717 | 0.886 | 0.048 | 0.18 s |
| (b2) Embeddings, same language only | θ = 0.6 | 0.934 | 0.563 | 0.702 | 0.879 | 0 | |
| **(b3) Embeddings, θs = 0.55 / θx = 0.45** | | **0.835** | **0.725** | **0.776** | **0.901** | 0.360 | <0.2 s |
| (b3) | θs = 0.6 / θx = 0.45 | 0.896 | 0.657 | 0.758 | 0.897 | 0.328 | |
| (c1) Agglomerative, average linkage | d = 0.5 | 0.804 | 0.691 | 0.743 | 0.885 | 0.208 | 0.014 s |
| (c2) HDBSCAN | mcs = 3 | 0.394 | 0.422 | 0.408 | 0.806 | 0.256 | 0.016 s |

**Without the Huawei event:**
- (b3) θs 0.55 / θx 0.45 scores pair F1 0.589 and B³ 0.899.
- (b) θ 0.55 scores pair F1 0.49 and B³ 0.885.

**Scale:** incremental embedding clustering over all 826 corpus items took 1.08 s, in pure Python with an O(n × live
clusters) loop.

**Cosine similarity of gold pairs** (text-embedding-3-small, title + summary), as median [p10–p90]:
- same-language, same-event: 0.673 [0.58–0.88];
- **cross-language, same-event: 0.405 [0.28–0.55]**;
- the 200 most similar cross-language **different**-event pairs: 0.369 [0.34–0.43].

## Findings
- **F-1. Embeddings clearly beat TF-IDF for event clustering within a language** (pair F1 0.70–0.72 against 0.37). At a
  usable precision, TF-IDF over title + summary misses most same-event pairs (recall 0.2–0.25), because different
  outlets word the same event differently. Korean and Chinese TF-IDF on character n-grams was no better. Cost of
  embeddings: about $0.002 for 826 items. Embeddings remove the hand-tuned per-language tokenisation.
- **F-2. Cross-lingual linking with raw multilingual embeddings is weak.** Same-event cross-language pairs score
  around 0.40, which overlaps the most similar unrelated pairs (around 0.37). A single threshold links only 5–22% of
  cross-lingual pairs. A separate cross-language threshold (0.45) lifts that to 33–36% and gives the best overall
  F1 (0.776). Below 0.45, precision collapses: θx 0.40 gives pair P 0.35. **Raw-text embeddings cannot reliably say
  "this KO story is that EN story."**
  - Candidate fixes, all INFERRED and to be tested in round 2:
    - translate headlines to English first (an LLM or MT call), then embed;
    - anchor links on shared named entities;
    - ask an LLM to confirm candidate cross-lingual pairs in the 0.35–0.5 band.
- **F-3. The incremental single-pass method is as good as the batch agglomerative comparator** (F1 0.72–0.78 against
  0.74) and suits streaming ingestion. **HDBSCAN performed poorly** on this sparse, mostly-singleton data (F1 0.41):
  it makes its own density choices and merges unrelated items.
- **F-4. Thresholds were picked on the same gold set they are scored on.** The best-setting numbers are optimistic.
  Treat θs ≈ 0.55–0.6 and θx ≈ 0.45 as starting points to re-tune on a held-out set.

## Limits
- **The gold set is small** (240 items, 28 multi-item events), **LLM-assisted, and half-checked.** Event granularity
  (for example the Huang saga) is a judgement call that moves recall a lot.
- **Pairwise metrics are dominated by one 19-item event.**
- **Title + summary only.** Full-text embeddings were not tested.
- **Text cap:** each item was cut to the title plus 400 characters of summary.
- **Window:** a 48 h window was assumed and not swept.
- **Environment:** two venvs were needed. The first venv under the long scratch path lost files to the Windows
  260-character MAX_PATH limit: `anthropic` and `scikit-learn` imports failed. The second was created at the same
  scratch location through a `subst R:` drive mapping. Anthropic was then called over plain HTTP.
