# Experiment 1: URL canonicalisation, exact hashing, near-duplicate and syndication detection (R6, 2026-11-25)

> **Status: Experimental result.** Measured on a feed sample collected on 2026-11-25; a model-assisted hand check, not a human one.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

All findings are TESTED unless they are tagged otherwise.

**Input:** `../event_clustering/corpus/items.jsonl`, 971 rows:
- 896 RSS entries from 23 publisher feeds (EN 224, KO 482, ZH 190);
- 75 GDELT DOC 2.0 artlist rows (EN, the Huawei verdict story).

The same article can appear in several feeds, and those repeats are kept on purpose so they can be measured.
`fulltext.jsonl` holds 60 pages fetched with trafilatura, after a robots.txt check (0 blocked). 57 of them have
300 or more characters.

**Scripts:**
- `dedup_experiment.py` writes `dedup_results.json` and `handcheck_sample.json`.
- `syndication_breakdown.py` writes `syndication_breakdown.json`.

**Shingling:** character 4-grams of NFKC-lowercased text. This is language-agnostic and needs no tokenizer for KO/ZH.

**Reference:** exact Jaccard over all pairs. 919 docs give 421k pairs in under 3 s, so an all-pairs check is cheap at
this size. MinHash and SimHash are scored against it.

## (a) URL canonicalisation and exact content hash

| Measure | Value |
|---|---|
| Rows | 971 |
| Distinct raw URLs | 920 |
| Distinct canonical URLs (courlan `normalize_url`, plus tracking-parameter strip, `www.`/`m.` strip, AMP and trailing-slash strip) | **920**. Canonicalisation merged **nothing** in this corpus. |
| Canonical URLs that appear in more than one feed (e.g. Yonhap `news.xml` and `international.xml`) | 49 |
| Exact content-hash duplicate groups (title + summary) among unique URLs | 8 |

- **Finding D-1.** Publisher RSS URLs are already clean. The 51 repeated rows are one URL listed in several feeds of
  the same publisher. An exact URL key catches all of them, and courlan added nothing on this corpus. Tracking
  parameters and AMP URLs appear when links come from social media or aggregators, which were not in this corpus.
  **Keep the canonicaliser anyway (it is cheap), but do not count on it for dedup.**
- **Finding D-2.** **Different URLs can carry the same content**, and only the content hash catches them. Two cases
  were seen:
  - France24 publishes one item at `/en/tv-shows/a-propos/20261123-a-war-of-...` and at `/en/a-war-of-...`.
  - GDELT rows from `chinanationalnews.com`, `iranherald.com` and `aninews.in` carry the identical ANI story.

  A URL key alone would count each of these as separate items.

## (b) Near-duplicates: MinHash-LSH against SimHash

### Title + summary (919 docs with 20 or more characters)

Pairs by exact Jaccard band: 0.9+: 435 · 0.7–0.9: 39 · 0.5–0.7: 527 · 0.3–0.5: 140.

| Method | Setting | Candidates | Recall vs exact pairs at or above the threshold | Precision vs exact | Time |
|---|---|---|---|---|---|
| MinHash-LSH, 128 perms | t = 0.5 | 1,036 | 0.989 | 0.956 | 0.83 s (signatures + index + query) |
| MinHash-LSH | t = 0.7 | 512 | 0.987 | 0.914 | 0.77 s |
| MinHash-LSH | t = 0.9 | 433 | 0.993 | 0.998 | 0.71 s |
| SimHash 64-bit | Hamming ≤ 3, vs J ≥ 0.9 | 432 | 0.991 | 0.998 | 2.8 s signing; all-pairs Hamming |
| SimHash | ≤ 6, vs J ≥ 0.7 | 436 | 0.920 | 1.000 | |
| SimHash | ≤ 10, vs J ≥ 0.5 | 449 | **0.449** | 1.000 | |

- **Finding D-3.** **Both methods find near-exact copies (J ≥ 0.9) equally well. Only MinHash-LSH is tunable down to
  the rewritten-copy range (J 0.5–0.7).** SimHash at Hamming ≤ 10 still recovers only 45% of the J ≥ 0.5 pairs. Short
  texts (titles and summaries) make SimHash coarse.
  **Recommendation:** MinHash-LSH, t ≈ 0.5 for the "same copy or syndication" flag, with t ≈ 0.9 as the "exact
  repost, collapse it" rule.

### Full text (56 docs with 300 or more characters)
Only 3 pairs reached J ≥ 0.5: iHeart stations carrying an identical story. Both methods found all 3 at every
setting. **The full-text subset is too small to separate the methods.** The one cross-outlet pair in the 0.3–0.5 band
was KSL against Free Malaysia Today on the Huawei verdict: the same event, with different copy.

## What the near-duplicate pairs actually are (title + summary, J ≥ 0.5)

| Kind | Pairs | Example |
|---|---|---|
| Same registrable domain, different host | **907** | 44 `*.iheart.com` station sites carrying "Huawei Found Guilty On Multiple Federal Charges" |
| Cross-publisher, GDELT EN | 54 | ANI copy on 3 domains; Reuters headline variants (BusinessWorld vs Economic Times, J = 0.87) |
| Same source (revisions and boilerplate) | 38 | Yonhap "(종합)" updates republished under a new URL; France24 dual paths; **Guardian live-blog boilerplate (a false positive)** |
| Cross-publisher, KO RSS | 2 | Yonhap to SBS rewrites ("러시아서 북한인 절도범…" J = 0.54; "美민주, 트럼프 장남 투자사…" J = 0.63) |

- **Finding D-4. Source independence must be computed at the registrable domain (eTLD+1), not at the host.**
  - The 75 GDELT rows came from 75 distinct hosts but only 31 registrable domains, and 44 of the rows were iHeart.
  - Counting hosts would make one syndicated wire story look like 44 independent confirmations.
  - Even at eTLD+1, ANI and Reuters copy is spread across unrelated domains. So the corroboration count must be
    "distinct content clusters", not "distinct domains".
- **Finding D-5. Yonhap revisions** ("…(종합)", "…(2보)") are new URLs whose text is J 0.76–0.83 similar to the
  earlier version.
  - The data model must treat them as **revisions of one story**, keyed on the same publisher plus near-duplicate text
    within a time window.
  - They are not new items. Counting them as new would double-alert the desk.
- **Finding D-6. Korean syndication is a rewrite, not a copy.** SBS takes Yonhap stories but rewrites the headline
  (美 → 미국, 잡고보니 → 잡고 보니), which lands at J ≈ 0.55–0.65. A J ≥ 0.9 rule misses this entirely. t = 0.5 catches it.
- **Failure example.** Guardian live-blog summaries share boilerplate ("– as it happened" plus key-event text), and two
  unrelated live blogs scored J = 0.63. A Yonhap "[북한단신]" pair (two different items with a shared lead) scored
  J = 0.38. **Template text causes false near-duplicate flags. Strip known boilerplate per source before shingling.**
  Stripping "| station name" title suffixes changed only 3 of the 907 iHeart pairs.

## Hand-checked precision
I (an AI research agent) read both texts of every pair in a stratified sample. The judgement was "same story: a copy,
syndication or revision". This is the agent's judgement, not a human's.

| Band (title + summary) | Pairs checked | Same story |
|---|---|---|
| 0.9+ | 8 | 8 |
| 0.7–0.9 | 8 | 8 (5 Yonhap revisions, 3 AP/Reuters headline rewrites) |
| 0.5–0.7 | 8 | 8 (all iHeart) |
| 0.3–0.5 | 8 | 7 (the miss is the Yonhap 북한단신 pair) |
| Full text 0.9+ / 0.3–0.5 | 3 / 1 | 3 / 0 (the 0.3–0.5 pair is the same event with different copy) |

There is also one known false positive at J = 0.63 outside the sample (the Guardian live blog).
**Limits:**
- The sample is small: 32 + 4 pairs.
- The sample is dominated by iHeart pairs, because GDELT surfaced one heavily syndicated story.
- Precision at t = 0.5 on a corpus with many live blogs will be lower than 8 of 8.

## Recommendation for D5 (dedup)
1. Keep two keys: an exact canonical-URL key and a SHA-256 of the normalised title, summary and body.
2. Run MinHash-LSH (datasketch, 128 perms, char 4-grams, after per-source boilerplate stripping) with two thresholds:
   - t = 0.9 means "same item": collapse it.
   - t = 0.5 means "syndicated or revised copy": link it, do not delete it.
3. Tie revisions together by same publisher plus J ≥ 0.5 within 48 h.
4. Count sources by eTLD+1, and corroboration by distinct near-duplicate clusters.

SimHash is not needed.

**Limit.** No corpus here had UTM-laden or AMP URLs, so the canonicaliser is untested against them.
