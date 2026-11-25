# ADR-004 · Storage (D4): SQLite (WAL) + FTS5 with CJK bigram pre-tokenisation, behind a repository layer

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: Built.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Informs:** deliverable 11 §5 (DDL), ADR-009 (configurable backends).

## Context

- Volume: 23 feeds gave 571 unique items in 24 h (TESTED); about 100 feeds would give 2,500–5,000 items/day,
  1–2 M items/year (INFERRED) ([`technology/data-model-and-lifecycle.md`](../../technology/data-model-and-lifecycle.md) §5).
- Python's bundled SQLite 3.50.4 has FTS5 and `trigram` (TESTED, [`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) F-C-06).
- KO/ZH search (TESTED, [`experiments/korean-fts/results.md`](../../experiments/korean-fts/results.md)): `unicode61` recall 0.68 KO, **0.09 ZH**;
  `trigram MATCH` returns **0 rows for 2-character queries** (북한, 美国); `trigram LIKE` and CJK bigram pre-tokenisation
  both reach recall 1.00 with 0 nonsense hits.
- `kiwipiepy` ships a statistical language model; whether it fits the no-local-inference policy is a pending project-owner decision
  ([`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) F-C-05).

## Options considered

| Option | Verdict | Evidence |
|---|---|---|
| **SQLite WAL + FTS5** | Fits MVP volume; zero operations; single file backup | TESTED FTS; INFERRED scale |
| PostgreSQL + pgvector (+ pg_trgm/pg_bigm) | Headroom, multi-writer, row-level security; a server to run; pg_trgm has the same short-query issue (INFERRED, untested) | `DATA_MODEL…` §5 |
| OpenSearch/Elasticsearch (nori, smartcn) | Best analysers; JVM cluster; over-provisioned | same |
| Meilisearch (MIT + BUSL-1.1 EE files), Typesense (GPL-3.0), Tantivy | Korean support UNVERIFIED; licence flags | [`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) F-C-06, §3 |

Tokenizer sub-options: (a) `trigram` + `LIKE` for queries under 3 characters; (b) bigram pre-tokenised column in
`unicode61`; (c) `kiwipiepy` morphology.

## Decision

1. **SQLite in WAL mode, one file per instance**, `busy_timeout` set, one writer connection owned by the pipeline thread;
   web requests that write (editorial verdicts, profile edits) go through the same write queue.
2. **Search = FTS5 over a pre-tokenised, contentless index** (`contentless_delete=1`): Hangul and Han runs are split into
   overlapping character bigrams at insert and at query time; Latin text stays as `unicode61` words. Option (b) is chosen
   over (a) because it keeps BM25 ranking for every query length (`korean_fts/RESULTS.md` "Recommendation for D4").
   The indexed text is title + feed summary + retained body (only where `storage=full`) + AI Korean headline/summary +
   entity names in original and Korean forms (cross-lingual recall without vectors, `06_AI…` §5).
3. **No `kiwipiepy`, `jieba` or other analyser** is a dependency. Bigram already reaches recall 1.00; a morpheme analyser
   could only improve ranking (round-2 question).
4. **No vector index in the MVP.** Event clustering keeps centroids of open events (48 h window, a few thousand items)
   in memory and as BLOBs; `sqlite-vec` 0.1.9 (TESTED loadable, pre-1.0) is deferred until archive-wide semantic search is
   needed.
5. **All SQL lives behind a repository layer** with a `SearchIndex` interface; DDL stays in the portable subset R6 wrote
   (TEXT ISO-8601 UTC timestamps, INTEGER keys, JSON as TEXT), so a PostgreSQL implementation is a new adapter plus a data
   copy, not a rewrite.
6. A **known-answer + nonsense query regression suite** (R6's 10 + 3 queries per language) runs in CI.

## Consequences

- Backup is `VACUUM INTO` daily plus off-host copy; restore is a file copy (deliverable 11 §8).
- One writer means pipeline throughput is bounded by single-thread write speed; adequate at MVP volume (INFERRED).
- Contentless FTS cannot return column text; result rendering reads the base tables (and applies `DisplayPolicy`).
- `contentless_delete=1` is DOCUMENTED for SQLite ≥ 3.43 (https://www.sqlite.org/fts5.html) but was not exercised in
  phase 1: verify in the first backlog task.

## Evidence

[`technology/data-model-and-lifecycle.md`](../../technology/data-model-and-lifecycle.md) §3, §5 · [`experiments/korean-fts/results.md`](../../experiments/korean-fts/results.md),
`fts_results.json` · [`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) F-C-05, F-C-06 ·
[`technology/computational-methods-report.md`](../../technology/computational-methods-report.md) §1.

## Reversal triggers (R6's migration triggers, any one)

1. More than one concurrent writer process, or `SQLITE_BUSY` above 1% of writes.
2. More than 10 M revisions, or FTS p95 above 300 ms.
3. A multi-tenant service needing per-client access control in one database (ADR-009 SaaS path).
4. Vector search beyond the live window.
5. The project owner approves `kiwipiepy` under the no-local-inference policy and a ranking evaluation shows a gain.
