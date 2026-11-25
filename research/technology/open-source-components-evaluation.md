# Components evaluation — libraries as dependencies (R4, 2026-11-25)

> **Status: Experimental result.** Library evaluation backed by smoke tests run on 2026-11-25.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Informs:** D1 (can libraries cover every pipeline stage?), D4 (storage), D8 (delivery surface).
**Registry:** [`technology/components-registry.csv`](components-registry.csv) (60 rows; every row has tag, source URL, date).
**Smoke test:** [`experiments/component-smoke/`](../experiments/component-smoke) (`smoke.py`, `smoke_supplement.py`, `results.json`,
`supplement_results.json`, `requirements.txt`, `meta_2026-11-25.json`). All dates 2026-11-25.
**Not covered here:** complete apps (R3), Korean FTS5 and dedup/cluster accuracy (R6), AI providers (R7), legal review of
licences (R9, but AGPL/GPL items are flagged below).

## 1. Answer for D1

Every stage of the text pipeline has at least one maintained, permissively licensed Python library, and the core chain was
run end to end against live sources. The chain below fetched, parsed, extracted, dated, canonicalised and fingerprinted a
real English article (BBC) and a real Korean article (Yonhap), and served the result over a JSON API. **INFERRED: library
assembly (K-B) is technically sufficient for the text and feed half of the system.** What libraries do not supply: the
per-source Korean cleanup rules, the wire services themselves (AP/Reuters are not reachable, see R5), and anything about
video (R8). No stage needed a local model.

Recommended spine (all TESTED unless marked):

| Stage | Pick | Runner-up |
|---|---|---|
| Feed ingest, state, scheduling | `reader` 3.27 | `feedparser` + own SQLite table |
| Feed parsing (stateless) | `feedparser` 6.0.14 | `fastfeedparser` 0.6.5 |
| Article extraction | `trafilatura` 2.4.0 | `readability-lxml` 0.9 |
| Metadata (date, JSON-LD) | `htmldate` + `extruct` | trafilatura's own metadata |
| URL canonicalisation | `courlan` (+ strip fragments) | hand-written rules |
| HTTP client | `httpx` | `requests` (already a reader dependency) |
| Near-duplicate | `datasketch` MinHash/LSH | `simhash` (stale) |
| Title similarity | `rapidfuzz` | stdlib `difflib` |
| Language ID | script ratio (Hangul vs Latin), then `py3langid` (INFERRED for the script rule) | `langdetect` |
| Korean tokens | SQLite FTS5 `trigram` (available) first; `kiwipiepy` if morphology is needed (flagged) | python-mecab-ko (UNVERIFIED on Windows) |
| Storage + search | SQLite + FTS5 (+ `sqlite-vec` if embeddings are adopted) | PostgreSQL (+ pgvector) |
| Read-only UI/API | `datasette` | FastAPI |
| Scheduler | OS scheduler or reader's own `update_after`; `APScheduler` 3.x inside a process | `huey` (SQLite backend) |
| Notification | `apprise` | stdlib `smtplib`, Telegram/Slack direct |
| MCP surface | `datasette-mcp` first (see [`technology/mcp-servers-evaluation.md`](mcp-servers-evaluation.md)) | custom FastMCP/SDK server |

## 2. Per-stage findings

### F-C-01 · `reader` can be the spine for feed ingest, state and scheduling
- Question: does a maintained library handle fetch, store, update scheduling and unchanged-detection?
- Finding: `lemon24/reader` 3.27 (BSD-3, released 2026-10-11, pushed 2026-11-23) stored 120 Yonhap entries into a SQLite file,
  set `update_after` (a default second `update_feeds` returned nothing until it is due), and a forced second update reported
  `new=0, unmodified=120`. It parses with feedparser internally. Other facts from the code: it needs Python 3.12+, has 6 core
  dependencies, ships entry/enclosure dedupe plugins and optional FTS5 search (`porter unicode61`, which does not segment
  Korean), and its default plugin `.ua_fallback` retries a 403 with another user agent.
- Evidence: TESTED `experiments/component-smoke/results.json` (raw results not published: they contain third-party article snippets) (step `reader`); VERIFIED reader source in the
  scratch venv (`reader/_parser/__init__.py`, `reader/_parser/http.py`, `reader/_storage/_search.py`).
- Limits: one feed, one run. `make_reader()` has no public user-agent argument (signature read), so a descriptive UA needed a
  `requests.Session` patch; the `.ua_fallback` plugin should be disabled (`plugins=[]`) to respect the access-ethics rule.
  The feed's cached ETag lives in `caching_info`; I did not inspect it.
- Implication: K-B starts from reader plus a few extraction steps rather than a blank page. The two obligations (UA patch,
  plugin off) go into the starter prompt.

### F-C-02 · Conditional GET depends on the publisher, and libraries differ
- Finding: `feedparser.parse(url, etag=, modified=)` works: a PyPI RSS feed (control) answered the second call **304 with 0
  entries**. Yonhap's feed returned ETag and Last-Modified but answered **200 with all 120 entries** when both were sent back
  (two independent trials). The BBC world feed returned **no validators at all**. `fastfeedparser` has no ETag handling (no
  match for etag/If-None-Match/If-Modified-Since in its source; the same search finds them in reader). `atoma` parses bytes
  only.
- Evidence: TESTED `supplement_results.json` (`a_conditional_get_*`); VERIFIED source greps.
- Limits: two publishers, a few minutes apart; Yonhap may honour validators at other times.
- Implication: do not rely on 304 savings for Korean broadcasters' feeds. Dedupe by content hash (reader does) and by entry
  id, and set polling intervals by source (R5 owns the policy). A 96 KB feed polled every minute is about 140 MB/day.

### F-C-03 · trafilatura is the best-supported extractor, with a Korean boilerplate caveat
- Finding (one page per site, no ground truth, lengths in characters):

| Library | BBC (English) | Yonhap (Korean) | Metadata |
|---|---|---|---|
| trafilatura | 4297 | 1988 | title, author, date, JSON output |
| readability-lxml | 3994 | 2035 | title only |
| newspaper4k | 2879 | **ImportError** (needs `nltk`) | title, authors, date |
| goose3 | 1185 | **0** (target_language=ko) | title, date |

  trafilatura's Korean text kept three Yonhap boilerplate lines (a "read with the full article" notice, the 송고 timestamp line,
  a Google-search notice); BBC output began with the title and a "- Published" fragment. `htmldate` returned 2026-11-24 and
  2026-11-25, matching the feed dates. `extruct` found JSON-LD with `datePublished` on both pages (`ReportageNewsArticle`,
  `NewsArticle`). `news-please` is archived on GitHub.
- Evidence: TESTED `results.json`, `supplement_results.json` (b, d); VERIFIED `gh api repos/fhamborg/news-please` archived=true.
- Limits: n=1 page per site; "longer" is not "more correct". R6's extraction experiments should score against hand-marked
  bodies. Goose3 was not tuned for Korean.
- Implication: extraction = trafilatura, plus a small per-source regex list for Korean boilerplate, plus JSON-LD as a
  cross-check for title and date.

### F-C-04 · Canonicalisation and dedup components work at smoke level
- Finding: `courlan.check_url` returns the feed link without the BBC `at_medium/at_campaign` parameters; `normalize_url` kept a
  `#fragment`, so fragments need a separate strip. One near-duplicate pair (original vs 90% copy with a new tail) scored
  MinHash Jaccard 0.883, LSH hit, SimHash Hamming 3, rapidfuzz token_set 99.5; the unrelated pair scored 0.0, no hit, 34, 17.7.
- Evidence: TESTED `results.json` (steps `trafilatura_htmldate_courlan_extruct_readability`, `datasketch_simhash_rapidfuzz`).
- Limits: one pair each. That separates identical text from unrelated text; it says nothing about same-event rewrites,
  translated text or wire-copy variants. That is R6's experiment. `simhash` last released 2022-03 and emits a
  SyntaxWarning on Python 3.13.
- Implication: datasketch and rapidfuzz are fine as dependencies; thresholds are an R6 output.

### F-C-05 · Language ID and Korean tokenisation: what is statistical, what is neural
- Finding: `langdetect` (naive Bayes over character n-grams, last release 2021) and `py3langid` (4.6 MB, linear classifier) both
  labelled the English and Korean samples correctly. `lingua-language-detector` is statistical n-gram too but ships a 172 MB
  wheel. `fasttext-langdetect` wraps a fastText model and `gcld3`-style neural detectors exist: both conflict with the compute
  policy. `kiwipiepy` 0.25.1 (Apache-2.0) tokenised a Yonhap headline correctly (NNP/NNG/JKB tags); first call took 5.4 s
  (lazy load). `konlpy` is GPL-3.0 and unreleased since 2022-01. `jieba` (MIT, dictionary + HMM) fits the Chinese plus.
- Evidence: TESTED `results.json` (`language_id`, `kiwipiepy_statistical_morph_analyzer`); DOCUMENTED PyPI/README for model types.
- Limits: **kiwipiepy is a gray area**: it ships a statistical language model plus dictionary rather than a neural network. I ran it
  because the brief asks to classify such tools and the call is millisecond-scale, but the project owner should confirm that it counts as
  "dictionary/statistical" under the no-local-inference policy before it enters the build. Language ID was one sample per language.
- Implication: Korean vs English needs no library (Hangul/Latin character ratio); keep a statistical detector only for
  Chinese/other. For Korean search, start with FTS5 trigram (no analyser) and let R6's test decide whether kiwipiepy is needed.

### F-C-06 · Storage and search: SQLite is sufficient for the library layer (D4 input)
- Finding: Python's bundled SQLite 3.50.4 on this Windows machine has FTS5 and the `trigram` tokenizer. `sqlite-vec` 0.1.9
  loaded as an extension and a `vec0` k-nearest-neighbour query returned the expected row. Datasette served a SQLite file with
  `--immutable` and returned entry rows from `/demo/entries.json?_shape=array`. Meilisearch is MIT plus BUSL-1.1 for its
  Enterprise files; Typesense is GPL-3.0; OpenSearch is Apache-2.0 on a JVM cluster; pgvector uses the PostgreSQL License.
- Evidence: TESTED `results.json` (`sqlite_fts5_sqlitevec`, `datasette_over_sqlite`); VERIFIED LICENSE files via `gh api`.
- Limits: availability only. No relevance, Korean-query or scale test (R6/E). Meilisearch and Tantivy Korean support are
  UNVERIFIED. `sqlite-vec` is pre-1.0.
- Implication: nothing in the library survey forces PostgreSQL or a search server. D4 tilts to SQLite + FTS5 unless R6's Korean
  test or a multi-writer requirement says otherwise.

### F-C-07 · Scheduling and delivery need very little (D8 input)
- Finding: an MVP needs one polling loop. reader's `update_after` is already a per-feed schedule; the OS scheduler (Task
  Scheduler/cron/systemd timer) can run `update_feeds`; `APScheduler` 3.11.3 ran an interval job three times in 3.3 s. RQ and
  Celery need a broker; Prefect (57 core deps) and Dagster (31) are workflow platforms. Apprise 2.3.0 loaded 175 notification
  schemas and accepted Telegram, Slack and mail URLs without sending anything.
- Evidence: TESTED `results.json` (`apscheduler_in_process`, `apprise_url_parse_only`, `reader`); DOCUMENTED PyPI metadata.
- Limits: no real message was sent (no credentials by design); Telegram Bot API and Slack webhook behaviour is DOCUMENTED only.
- Implication: no queue, broker or orchestrator in the MVP. Digest, alert and API surfaces are small code on top of SQLite.

## 3. Licence and policy flags (for R9 and the project owner)

| Item | Flag |
|---|---|
| RSSHub, Firecrawl | AGPL-3.0 (VERIFIED GitHub licence). Usable as an unmodified separate service; R9 should confirm obligations. |
| Typesense | GPL-3.0 server. |
| Meilisearch | MIT plus BUSL-1.1 files (VERIFIED LICENSE). |
| konlpy | GPL-3.0, stale since 2022 (REJECTED). |
| BERTopic, fasttext-langdetect | Default configuration needs a local embedding/ML model: conflicts with the no-local-inference policy. |
| kiwipiepy | Statistical LM shipped in the wheel: flagged as a gray area (F-C-05). |
| news-please | Archived upstream (REJECTED). |
| reader `.ua_fallback`, httpx last release 2024-12 | Disable the retry-with-other-UA plugin; httpx maintenance is slow but the repo is active (pushed 2026-11-16). |

## 4. What was not established

- Per-site extraction quality beyond two pages; no scoring against hand-marked bodies (R6).
- Korean FTS5 relevance, kiwipiepy-versus-trigram search quality (R6).
- crawl4ai, Playwright, Scrapy, RSSHub, Meilisearch, Tantivy, river, hdbscan, python-mecab-ko were surveyed from metadata only
  (DOCUMENTED/VERIFIED metadata, not run). Reason: none can change D1/D4/D8 given a working core chain.
- Speed: the step timings in `results.json` include imports and cold starts, so they are not a benchmark.
- Searches run for discovery: PyPI JSON API for 49 packages, `gh api` for 56 repos, GitHub `gh search repos` ("datasette mcp",
  "rss mcp server"), the official MCP registry (see [`technology/mcp-servers-evaluation.md`](mcp-servers-evaluation.md)).
