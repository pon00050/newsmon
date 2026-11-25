# Experiment 3: SQLite FTS5 for Korean and Chinese search (R6, 2026-11-25)

> **Status: Experimental result.** Tokeniser comparison on a small Korean and Chinese item set.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Question:** is SQLite FTS5 adequate for KO/ZH search in an MVP?
**Answer: yes, if you pick the tokenizer correctly. Use `trigram`-indexed `LIKE` or a deterministic CJK
character-bigram pre-tokenisation. The default `unicode61` tokenizer is not adequate.** TESTED.

## Setup
- **Engine:** SQLite 3.50.4 from the Python 3.13.7 stdlib. FTS5 and the `trigram` tokenizer are built in.
- **Documents:** title and summary from the R6 corpus, deduplicated by text. That gives **460 KO docs** (Yonhap, Donga,
  Kyunghyang, SBS) and **177 ZH docs** (VOA Chinese, RFI Chinese, Chinanews, CNA Taiwan). Input:
  `../../event_clustering/corpus/items.jsonl`. The run used an RSS-only snapshot of it, with identical KO and ZH rows.
- **Ground truth:** a document is relevant to a query when it contains the query string as a substring.
- **Queries:** 10 known-answer queries and 3 nonsense queries per language. The queries include 2-character terms,
  which are common in KO and ZH: 북한, 미국, 중국, 中国, 美国, 华为, 北约, 日本.
- **Methods compared:**
  - A: `unicode61`, phrase query.
  - B: `unicode61` with a prefix query (`"term"*`).
  - C: `trigram` with `MATCH`.
  - C2: `trigram` with `LIKE '%term%'`.
  - D: character-bigram pre-tokenisation, Lucene-CJKAnalyzer style: Hangul and Han runs are split into overlapping
    bigrams, then stored in `unicode61`, and the query is a phrase of bigrams.
  - E: jieba pre-tokenisation, ZH only. Jieba is a dictionary plus HMM segmenter, not neural.
- **Files:** script `fts_experiment.py`; outputs `fts_results.json` (per query and method) and [`experiments/korean-fts/fts-summary.md`](fts-summary.md)
  (the full tables).

## Results (micro-averaged over the known-answer queries)

| lang | method | recall | known queries with 0 hits | nonsense hits |
|---|---|---|---|---|
| ko | A unicode61 | 0.684 | 0 | 0 |
| ko | B unicode61 prefix | 0.981 | 0 | 0 |
| ko | C trigram MATCH | 0.458 | **3** (every 2-char query) | 0 |
| ko | **C2 trigram LIKE** | **1.000** | 0 | 0 |
| ko | **D bigram pre-tok** | **1.000** | 0 | 0 |
| zh | A unicode61 | **0.088** | 6 | 0 |
| zh | B unicode61 prefix | 0.595 | 1 (习近平: 0 of 10) | 0 |
| zh | C trigram MATCH | 0.444 | 5 (every 2-char query) | 0 |
| zh | **C2 trigram LIKE** | **1.000** | 0 | 0 |
| zh | **D bigram pre-tok** | **1.000** | 0 | 0 |
| zh | E jieba pre-tok | 0.912 | 0 | 0 |

Precision against the substring truth is 1.000 for every method. **That is by construction, not a finding.**
Substring methods cannot return a non-substring. The nonsense controls returned 0 hits for every method, so a null
from any of these methods is trustworthy as a null.

## What the numbers mean
1. **`unicode61` fails on Chinese** because Chinese text has no spaces: a whole clause becomes one token. **It loses about
   30% on Korean** because particles attach to the noun. "대통령이" does not match "대통령" (17 of 75 hits). A prefix
   query rescues most Korean cases (0.98). It does not rescue Chinese, because the term is rarely at the start of a
   run (习近平 got 0 of 10).
2. **`trigram` MATCH silently returns nothing for queries shorter than 3 characters.** In Korean and Chinese, the
   short queries include the most important entity names: 북한, 미국, 中国, 美国. This is the most dangerous failure
   in the experiment, because an empty result looks like "no news". `trigram` with `LIKE` is still correct for 2-char
   queries. Those queries fall back to a scan, which is fast at MVP scale: every query here took under 5 ms.
3. **Bigram pre-tokenisation is complete and indexable** for every query length of 2 characters or more. It costs one
   deterministic function at insert time and at query time.
4. **jieba adds nothing for search.** It loses recall where its segmentation disagrees with the query: 中国 42 of 45,
   美国 47 of 60. Recall is the property that matters for monitoring.

## Limits
- The corpus is small: 637 docs. Query time and trigram index size at 10^6 docs were not measured. A trigram index is
  known to be several times larger than the text it indexes; that figure is UNVERIFIED and needs a round-2 measurement.
- Substring truth over-counts semantically. For example, Korean "이란" can be the grammatical ending "~이란" as well as
  Iran. I checked all 22 occurrences of 이란 in the KO set: all 22 meant Iran, so no false positive was seen here. On
  a larger corpus, expect a few false positives of this kind from short Korean queries.
- No ranking quality (BM25) evaluation, and no morpheme analyser for Korean. Kiwi and Mecab-ko were not installed. The
  bigram method already reached recall 1.0, so a morpheme analyser could only improve ranking or precision.
  That is a round-2 question.

## Recommendation for D4
SQLite FTS5 is **adequate for KO/ZH in the MVP**. Use one of these:
- **(a)** a `trigram` table, with `LIKE` for queries of fewer than 3 characters and `MATCH` otherwise; or
- **(b)** a bigram pre-tokenised column. Option (b) keeps BM25 ranking for every query length.

**Never ship plain `unicode61` for KO/ZH**, and never send 2-character queries to trigram `MATCH`. Add a regression test
that runs the known-answer and nonsense queries above.
