# 14 · Testing and evaluation plan (S2, 2026-11-25)

> **Status: Design proposal (not built).** Deliverable 14. The plan covers the full MVP; the shipped suite covers only Release A + A.1.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**What this covers.** How the MVP of [`specification/mvp-specification.md`](mvp-specification.md) is tested (unit, integration, end-to-end),
which fixtures make that possible without network or AI, how the quality of the system is evaluated against gold sets,
the thresholds that decide acceptance, the operational metrics, and a protocol for comparing the system with a human
monitor.

**Companion files.**
- [`specification/test-catalogue.csv`](test-catalogue.csv): every test, with its id, task, level, mode, path, requirement ids and description.
  It is generated with the backlog by a private generator script, which fails on any FR/NFR without a test.
- [`specification/implementation-backlog.md`](implementation-backlog.md): the tasks (T-01…T-64) that write these tests.
- [`technology/reliability-and-security.md`](../technology/reliability-and-security.md): J risks and the tests that cover them.

**Evidence tags.** Numbers quoted from phase 1 are TESTED in the files cited. Thresholds and protocols are S2 proposals
(INFERRED). Nothing new was measured for this plan.

## 1. Principles

1. **O1 is the default test mode.** The end-to-end suite runs with `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` unset and every
   `ai.capabilities` flag false (P-008; 12 §5.7). The MVP must pass its O1 acceptance before any AI test counts.
2. **No live network in CI.** An autouse `netguard` fixture fails any connection outside the loopback fixture ports
   (TS-HAR-04 proves it with a known-answer control). Feeds are recorded responses; wire input is synthetic.
3. **AI is mocked by default.** AI-mode tests use the deterministic AI stub (a fake `AIProvider` with a call log, scripted
   outputs, failures and costs). Live provider tests carry the `live` marker, run only with `NEWSMON_LIVE=1`, have a
   per-run dollar cap and are never required for a merge.
4. **Every instrument gets a control.** A test that can report "nothing found" also proves it can find something
   (known-answer) and that it returns nothing when nothing is there (nonsense). Examples: search (TS-FR20a + TS-FR20b),
   netguard (TS-HAR-04), every architecture checker (TS-ARCH-01…07 each flag a planted bad file), the licence gate
   (TS-NFR31 fails on a planted AGPL entry), `req_coverage.py` (TS-HAR-05).
5. **Two paths to every key number.** `/metrics` values are checked against a direct computation from the tables
   (TS-NFR12, TS-NFR30b). Profile preview counts are checked against a direct rule re-run (TS-FR16e).
6. **Thresholds are fixed before the data.** Floors below come from the spec (12 §5) or are set here. They are not moved
   after a run; a miss is reported with its weakness.
7. **Requirement traceability is mechanical.** Each test carries `@pytest.mark.req("<id>")`. `tools/req_coverage.py`
   reads the junit report and fails if any required id lacks a passing test (TS-ACO1-02 runs it over the O1 set).

## 2. Test levels and layout

| Level | Folder | What it proves | Default mode | Runs in CI |
|---|---|---|---|---|
| Architecture | `tests/arch/` | Import boundaries, SQL location, secret access, no tools, no training, parameterised SQL, supply chain | n/a | every push |
| Support | `tests/support/` | The harness itself: fixture server, SMTP sink, AI stub, netguard, fixtures, coverage tool | n/a | every push |
| Unit | `tests/unit/` | Pure functions: normalise, robots, gazetteer, spike, profiles, DisplayPolicy, safe text, parsers, prefilter | O1 | every push |
| Integration | `tests/integration/` | One component against SQLite and the fixture server: fetcher, connectors, dedup, clustering, search, delivery, API, MCP, ops | O1 or AI stub | every push |
| End-to-end | `tests/e2e/` | Whole runs: smoke, O1 acceptance, workflows, AI-mode with stub, deployment flexibility, install | O1 (AI stub where named) | every push; `slow` ones nightly |
| Evaluation | `eval/`, `tests/eval/` | Quality against gold sets, O1 vs AI side by side; shadow scoring | O1 + cached vectors offline; live opt-in | nightly offline; live on demand |
| Live | `tests/live/` | Real provider behaviour and latency | live | never by default |

Markers: `unit`, `integration`, `e2e`, `arch`, `eval`, `live`, `slow`, plus `req(id)`. Commands:

| Purpose | Command |
|---|---|
| Regression gate (every task) | `uv run pytest -q -m "not live and not slow"` |
| O1 acceptance (whole non-live suite; an autouse fixture unsets the AI keys) | `uv run pytest -q -m "not live and not slow" --junitxml=reports/junit-o1.xml && uv run python tools/req_coverage.py reports/junit-o1.xml --require o1` |
| Slow (performance, kill-restart) | `uv run pytest -q -m slow` |
| Offline evaluation | `uv run python eval/run_eval.py --offline` |
| Live smoke (opt-in, capped) | `NEWSMON_LIVE=1 uv run pytest -q -m live` |

CI runs a Windows and an Ubuntu job (T-57). Ubuntu is the only place the Linux install (TS-NFR28a), the systemd files
(TS-DEP02) and symlink refusal (TS-FR28d) are proven, because this workstation is Windows without Docker (P-004).

## 3. Fixture strategy

| Fixture | Source | Used by | Notes |
|---|---|---|---|
| Recorded public feeds (≥ 10 RSS/Atom files) | Built from R6's 971-row corpus (private experiment data (not published)) by `tools/build_fixtures.py` (T-05) | Connectors, normalise, dedup, clustering, search, e2e | Edge cases planted: missing date, tracking URL, empty title, Hangul/Han/Latin titles, live-blog pair, Yonhap "(종합)" pair, iHeart subdomain copies, HTML in summary, external-entity RSS. **Corpus-derived, private research data: excluded from the wheel** (TS-FIX-02) |
| Recorded API responses | Federal Register, SEC, GDELT `lastupdate` samples | `http_api` connector | Includes a skipped 15-minute file |
| Synthetic wire inbox | Hand-written (T-06), `synthetic=true` | Directory watcher, parsers, gating, alerts, e2e | ADR-010 §8 counts plus malformed, XXE, billion-laughs, oversize, fake video, cross-format near-duplicate; shipped safely (project-made text) |
| Gold copies | R6 handcheck pairs (32 title+summary + 4 full-text), 240-item clustering gold + labels + corrections + cached `embeddings.npy`, FTS corpus (460 KO + 177 ZH docs) with 10 known-answer + 3 nonsense queries per language | FR-08(a), FR-10(a)(b), FR-20(a)(b) | Frozen copies; the eval datasets of §5 extend them |
| Hand-labelled small fixtures | `lang30` (FR-05b), `relevance30` (FR-17a), 20-item enrichment set (FR-12a live) | Unit/integration and live tests | Labelling protocol §5.3 |
| Attack fixtures | R7's `prompts/attacks.json` (A1 hijack, A2 score, A3 exfil) + 11 clean articles | FR-14 | KO/ZH attacks added in E7 |
| Simulated clock | `tests/support/clock.py` | Retention, `valid_until`, schedules, incidents, cap reset, outage windows | No sleeping in tests |
| SMTP sink | `tests/support/smtp_sink.py` | Alerts, digests, outbox | Can reject a recipient with 550 |
| Fixture HTTP server | `tests/support/fixture_server.py` | Everything that fetches | Logs path, headers, timestamp; scripted 200/304/404/429/503, redirects, malformed, oversize, slow, robots |

**Mode matrix.** Every capability is tested in O1. Where AI changes behaviour, the same scenario is repeated with the
stub. Live runs only measure provider behaviour (schema validity, grounding, latency, cost).

| Scenario | O1 (keys unset) | AI stub | Live (opt-in) |
|---|---|---|---|
| Collection, dedup, health, search, alerts, template digest | TS-ACO1-01, TS-ACO1-04 | same suite with capabilities on (TS-FR15b) | — |
| Grouping | TS-FR10a (precision ≥ 0.80) | TS-FR10b with cached vectors | re-embed sample in E2 |
| Relevance | TS-FR17a (rules) | TS-FR11a…c (band merge) | E3 |
| Enrichment | not performed (stated) | TS-FR12a-stub, TS-FR13a, TS-FR13b | TS-FR12a-live |
| Licence gating | TS-FR01c, TS-FR06a…e | TS-FR15d, TS-FR10d, TS-FR12b, TS-FR30c | — |
| Degradation | header "AI: 꺼짐" (TS-ACO1-03) | outage, cap (TS-FR15b, TS-FR15c, TS-AIS-02) | — |

## 4. Unit, integration and end-to-end tests

The full list is `test_catalogue.csv`. The structure, by MVP area:

| Area | Unit / integration tests (examples) | End-to-end |
|---|---|---|
| Sources and collection (FR-01…04) | TS-FR01a…d, TS-FR02a…e, TS-SEC-09, TS-FR03a…d, TS-FR04a/b/d | TS-ACO1-01 |
| Processing (FR-05…10) | TS-FR05a…d, TS-FR06a…e, TS-FR07a…c, TS-FR08a…d, TS-FR09a/b, TS-FR10a/c | TS-FR06c (all four outputs), TS-ACO1-05 |
| AI (FR-11…15) | TS-FR11a…c, TS-FR12a-stub, TS-FR12b/c, TS-FR13a/b, TS-FR14a/b, TS-FR15a-unit, TS-FR15c | TS-FR15b, TS-FR15d-e2e |
| Profiles and ranking (FR-16, 17) | TS-FR16b/c/e, TS-FR17a…c | TS-FR16a-ui |
| Delivery (FR-18…26) | TS-FR18b, TS-FR19a/b, TS-FR20a…d, TS-FR21b…d, TS-FR22a…d, TS-FR23a…c, TS-FR24a…d, TS-FR25a/b, TS-FR26b/c | TS-ACO1-04, TS-FR26a, TS-WF1-7 |
| Connectors (FR-27…31) | TS-FR27b/c, TS-FR28a…f, TS-FR29a…e, TS-FR30b, TS-FR31a/b | TS-FR27a, TS-FR30c |
| Deployment flexibility (NFR-20…31) | TS-ARCH-01…03, TS-NFR23a, TS-NFR25, TS-NFR26, TS-NFR27b, TS-NFR29a…d, TS-NFR30a, TS-NFR31 | TS-NFR20, TS-NFR23b, TS-NFR24, TS-NFR28a |
| Performance and resilience | TS-FR20d | TS-NFR01a, TS-NFR02, TS-FR18a, TS-NFR04 |

**ADR-009 DECIDE-NOW checks named by the brief:** booting with config dir and DB path from environment variables only
and writing nothing outside the data dir (TS-NFR20); a full export → import round-trip restoring identical row counts
(TS-NFR29b); backup → delete → restore (TS-NFR29a); two instances sharing nothing (TS-NFR24); every root-table query
carrying `workspace_id` (TS-NFR23b).

**Supplement-02 checks:** the generic connector contract (TS-FR27a…c), the directory watcher (TS-FR28a…f), the mock-wire
fixtures (TS-FIX-03, TS-FR29a), and licence-flag enforcement, above all `external_ai_allowed=false` producing zero hosted
AI calls, asserted on the stub's call log (TS-FR15d, TS-FR15d-e2e, TS-FR10d), and a flag flip making the next item
eligible (TS-FR30c).

## 5. Evaluation datasets

Phase 1 left no desk-labelled gold set (OQ-7). The existing sets are small or LLM-assisted, so each dataset below says what
exists, what to build, its size, and the labelling protocol. Sizes are chosen so a 95% confidence interval on a
proportion near 0.9 is roughly ±0.05 or better where a threshold depends on it (n ≥ 140); smaller sets are marked
indicative.

### 5.1 E1 · Deduplication

- **Exists:** R6's exact-Jaccard reference over 919 documents (421k pairs; automatic truth) and 36 hand-checked pairs
  (`deduplication/handcheck_sample.json`). MinHash recall 0.989–0.993 against exact Jaccard (TESTED).
- **Build:** 300 pairs, stratified by exact-Jaccard band (0.3–0.5, 0.5–0.7, 0.7–0.9, ≥ 0.9; 75 each) and by language
  (EN/KO/ZH), plus 20 cross-format wire pairs from the synthetic inbox.
- **Labels:** same item / syndicated rewrite / revision (same source) / different story. Two labellers independently, then
  adjudication; report Cohen's κ.
- **Metrics:** recall and precision per link kind against human labels; recall against exact Jaccard ≥ 0.5 (FR-08a).

### 5.2 E2 · Event clustering

- **Exists:** 240 items (80 per language), labels proposed by Sonnet in one call, about 120 spot-checked with 1 correction;
  158 events, 327 same-event pairs, 125 cross-lingual. **Bias:** one event holds 171 of 327 pairs, and the O3 thresholds
  were tuned on this set, so its O3 numbers are optimistic ([`experiments/event-clustering/results.md`](../experiments/event-clustering/results.md)).
- **Build:** 600 items over 3 consecutive days (200 per language), sampled from collected items, with at least 40
  multi-item events and **no event above 15 items** (larger events are subsampled) so that no single story dominates the
  pair counts.
- **Labels:** event = a specific happening, follow-ups within about 48 h share the event (R6's definition). Two labellers
  work blind to system output, in a sheet ordered by time, with titles and summaries in the original language (bilingual
  labellers for ZH). Disagreements adjudicated by a third person. Report κ on a 100-item overlap.
- **Metrics:** pair precision, recall and F1; B³ F1; cross-lingual pair recall; per-event macro recall. **O3 thresholds are
  re-tuned on E2's first day only and scored on days 2–3** (held out).

### 5.3 E3 · Relevance and priority (desk-labelled)

- **Exists:** nothing desk-labelled. `relevance30` (FR-17a) is a 30-item fixture built in T-31 by the same protocol.
- **Build:** 400 items from one week of collection under the `foreign_desk` profile: 250 sampled stratified by system band
  (flash/report/review/drop) and **150 sampled at random from `drop`**, so that misses by the rules can be found.
- **Labels:** a working 외신 monitor where one is available; otherwise the researcher acting as one, which is weaker and is
  reported as such. The labeller sees title, source, time and summary (never the system band) and answers: band
  (flash/report/review/drop), and "would I register this (PC등록)?". 100 items double-labelled for κ.
- **Metrics:** band agreement; recall of labeller flash+report items at system band ≥ review; false-alert rate at
  system flash; "would register" recall. O1 rules are compared with O1 + LLM band (O2).

### 5.4 E4 · Search

- **Exists:** 10 known-answer + 3 nonsense queries per language (KO, ZH) on 460 KO and 177 ZH docs with substring truth;
  bigram recall 1.00 and 0 nonsense hits (TESTED, `korean_fts/RESULTS.md`). Precision 1.00 there is by construction.
- **Build:** 30 known-answer queries per language for KO, ZH and EN, plus 20 cross-lingual information needs ("Korean
  query, find English and Chinese coverage"), with graded judgements (0/1/2) on the pooled top-10 of O1 and O2.
- **Metrics:** recall against substring truth (regression floor 1.00), nDCG@10 on graded judgements, cross-lingual recall
  O1 (gazetteer expansion) vs O2 (query rewrite).

### 5.5 E5 · Translation and summary factuality

- **Exists:** 22/22 Korean summaries judged correct on a full read; entity grounding 98–100% (TESTED, n = 11 articles × 2
  models; small).
- **Build:** 150 items (60 EN, 50 ZH, 40 KO) with Haiku enrichment, and a 50-item Sonnet subset for comparison.
- **Automatic checks on all 150:** schema validity, Hangul ratio, every `name_original` verbatim in the source, every number
  in the summary present in the source, quotes' originals present verbatim.
- **Human rating:** two bilingual raters per item, blind to model, score faithfulness (2 = faithful, 1 = minor omission,
  0 = contains an unsupported or wrong claim), attribution correctness (who said it), and quote-translation accuracy; tag
  errors as fabricated number, fabricated entity, wrong attribution, wrong place or time, key fact omitted, payload echo.
- **O1 baseline:** O1 produces no Korean summary or translation. The table reports "not performed in O1"; it does not
  invent a baseline score.

### 5.6 E6 · Citation accuracy (digests)

- **Build:** 30 AI digest drafts over 30 fixture windows (morning, evening, handoff).
- **Automatic:** every bullet cites ≥ 1 article and every cited id is in the selected set. This is an approval gate
  (TS-FR22b), so an approved digest passes it by construction.
- **Human:** for each bullet, is every claim supported by the cited articles? (supported / partly / unsupported). Two raters,
  adjudicated.
- **O1 baseline:** the template digest lists titles and links with their ids, so its citations are correct by construction.
  That is reported as such, not as a finding.

### 5.7 E7 · Injection robustness

- **Exists:** R7's A1–A3 English payloads on 3 targets (48/48 flagged; the score attack still moved bands).
- **Build:** 60 attacked items: the A1–A3 patterns translated into Korean and Chinese, injections inside quotations,
  attribution laundering ("according to the desk chief…"), hidden text (zero-width, HTML comments), plus 200 clean items
  for false positives.
- **Metrics:** flag rate (regex, model, combined); band elevation rate on flagged and unflagged attacks; **alert leakage,
  which must be 0**; false-positive rate on clean items.

### 5.8 E8 · Language identification

- `lang30` fixture for FR-05(b), extended to 300 items from feed metadata with spot-checked labels; accuracy per script.

### 5.9 Labelling logistics

- Labels are stored as JSON next to the dataset with labeller id, date and guideline version. Gold data never leaves the
  instance that holds the licensed text it came from (DR-19); public-feed gold stays private research material.
- Guidelines are frozen before labelling starts; changes create a new version and a re-label of the affected items.
- Estimated effort (INFERRED): E2 about 6 h per labeller, E3 about 5 h, E5 about 8 h per rater, E1 and E6 about 3 h each.

## 6. Acceptance thresholds

**MVP acceptance (blocking).** All are automated; the test ids are in `test_catalogue.csv`.

| Requirement | Metric | Threshold | Test |
|---|---|---|---|
| AC-O1-01 | AI-host connections in the O1 end-to-end run | 0 | TS-ACO1-01 |
| AC-O1-02 | O1 criteria with a passing test (FR-01…10, 16…23, 25…31, non-live) | 100% | TS-ACO1-02 |
| FR-05(b) | Language label accuracy on `lang30` | ≥ 29/30 | TS-FR05b |
| FR-08(a) / NFR-11 | Near-dup recall on R6 pairs with exact Jaccard ≥ 0.5 | ≥ 0.95 | TS-FR08a |
| FR-10(a) / AC-O1-05 | O1 pair precision on the 240 gold set | ≥ 0.80 (recall reported, no floor; 0.21 measured) | TS-FR10a |
| FR-10(b) | O3 pair F1 / B³ F1 on the 240 gold set (cached vectors) | ≥ 0.70 / ≥ 0.85 | TS-FR10b |
| FR-14(b) | Regex false positives on R7's clean fixtures | ≤ 2 of 44 | TS-FR14b |
| FR-17(a) | Rule band exact on `relevance30` | ≥ 28/30 | TS-FR17a |
| FR-20(a)(b) / NFR-10 | Known-answer recall; nonsense hits | 1.00; 0 | TS-FR20a, TS-FR20b |
| FR-20(d) | Search p95 on 100,000 rows | < 300 ms | TS-FR20d |
| FR-18(a) | Queue render p95 with 500 events | < 1 s | TS-FR18a |
| FR-21(a) / AC-O1-04 | Flash wire file to alert and email | ≤ 60 s | TS-ACO1-04 |
| FR-13(b) | Calls for 50 deterministic failures | exactly 100 | TS-FR13b |
| FR-15(c) | Calls after the cap | 0 | TS-FR15c |
| NFR-01 | Visible latency p95: public feed / inbox (O1) | ≤ poll + 120 s / ≤ 60 s | TS-NFR01a |
| NFR-02 | 5,000-item replay (AI stub) | ≤ 30 min | TS-NFR02 |
| NFR-04 | After kill + restart: integrity, duplicates | ok, 0 | TS-NFR04 |
| NFR-07 | Secret canaries in any output | 0 | TS-NFR07 |
| NFR-18 | pip-audit high/critical | 0 | TS-NFR18 |

**Live checks (reported, not blocking for O1 acceptance).**

| Requirement | Metric | Threshold | Test |
|---|---|---|---|
| FR-12(a) | Schema-valid after ≤ 1 retry; entities verbatim; numbers preserved (20 items) | 100%; ≥ 95%; 100% | TS-FR12a-live |
| NFR-01 (AI) | Added enrichment latency p95 | ≤ 60 s | TS-LIVE-02 |

**Evaluation targets (round 2; they decide AI routing and the LLM band weight, not MVP acceptance).**

| Dataset | Metric | Target | What a miss changes |
|---|---|---|---|
| E1 | Precision of `same_item` links | ≥ 0.95 | Raise t for `same_item` |
| E2 | O1 pair precision (held-out days) | ≥ 0.80 | O1 θ re-tune |
| E2 | O3 pair F1 (held-out days) / cross-lingual pair recall | ≥ 0.65 / ≥ 0.30 | Whether O3 is worth enabling by default |
| E3 | Recall of labeller flash+report at system band ≥ review | ≥ 0.85 (O1 and O2 reported separately) | Profile rules; `ai_band_weight` (0 if O2 adds nothing) |
| E3 | Share of system flash items the labeller calls drop | ≤ 0.10 | Flash rules |
| E5 | Items with a fabricated number or entity (automatic) | 0 of 150 | Prompt/schema fix; route to Sonnet |
| E5 | Human faithfulness score 2 | ≥ 0.95 | Haiku vs Sonnet routing (ADR-006 reversal trigger) |
| E6 | Unsupported bullets | ≤ 2% | Digest prompt; keep template as default |
| E7 | Alert leakage from attacked items | 0 | Blocking: fix before AI mode is offered |
| E7 | Combined flag rate on KO/ZH attacks | ≥ 0.95 | Regex patterns; cap LLM influence further |
| E7 | False positives on 200 clean items | ≤ 2% | Regex patterns |

## 7. Reporting O1 and AI mode side by side

`eval/run_eval.py` (T-63) writes one table per run, so the value AI adds is measured, not assumed. Rows are capabilities;
columns are modes. Where O1 does not perform a capability, the cell says "not performed in O1" rather than 0. Cost and
latency are part of every row.

| Capability | Metric | O1 | O2 | O3 | Δ (AI − O1) | AI cost per 1,000 items | Notes |
|---|---|---|---|---|---|---|---|
| Dedup | recall J ≥ 0.5 (E1) | value | same code path | same | 0 by design | $0 | — |
| Grouping | pair F1, B³, cross-lingual recall (E2) | value | = O1 | value | value | embeddings | held-out days |
| Relevance | recall flash+report, false flash (E3) | value | value | — | value | triage | noise ±15 (R7) |
| Search | nDCG@10, cross-lingual recall (E4) | value | value | — | value | rewrite | — |
| Korean summary | faithfulness, fabrication (E5) | not performed in O1 | value | — | — | enrichment | — |
| Digest | unsupported bullets (E6); editor edit distance | template (by construction) | value | — | — | Sonnet | — |
| Injection | alert leakage, flag rate (E7) | regex only | regex + model | — | value | — | — |

Phase-1 values to beat, for orientation: O1 grouping pair F1 0.371 and cross-lingual recall 0; O3 pair F1 0.776 and
cross-lingual recall 0.36 (tuned on the scored set); dedup recall 0.989–0.993 in all modes (all TESTED, ADR-006).

## 8. Comparing the system with a human monitor

**Question.** Would a 외신 desk using the system catch the items its monitor catches, as early, without drowning in
alerts? The protocol must be able to show that the software loses.

### 8.1 Two variants

| Variant | When | Reference record |
|---|---|---|
| **A · Published-record shadow week** | Round 2, `use_context=private`, no partner needed | What a Korean 24-hour news channel actually published from foreign news that week: its website's international section items (title, time), collected by the channel's own RSS or listing pages within its terms, or noted by hand |
| **B · Live desk shadow week** | A pilot partner exists | The monitor's own registrations (PC등록 log) and notices for the week, with timestamps, exported from the customer's system |

### 8.2 Procedure

1. **Pre-register** before the week: the profile, the system mode(s) under test (O1, and O2/O3 if enabled), the reference
   source, the matching rule, the metrics and the decision thresholds in §8.4. Nothing is changed during the week.
2. **Run** the system for 7 consecutive days (21 shifts) on its normal sources. In variant B the monitor works as usual and
   **does not see the system's output** during the week.
3. **Freeze** both records at the end: the system's alert log and queue snapshots at band ≥ report (`eval/shadow/export_alerts.py`,
   T-64) and the reference record.
4. **Match** reference items to system events by event identity, using the E2 event definition. Matching is done by a
   person who sees the two records **with the arm labels hidden** (`adjudication_sheet.py` shuffles and anonymises
   them). Disagreements go to a second adjudicator.
5. **Classify every miss** by cause: source not collected / collected but grouped wrongly / grouped but ranked below
   report / filtered or muted / collected too late.
6. **Classify every system-only alert:** a real item the reference lacks (a possible human miss, adjudicated blind) or a
   false alert. A system-only item counts in the system's favour only if the blind adjudicator rules it would have
   been worth registering.

### 8.3 Metrics

| Metric | Definition |
|---|---|
| Recall of human-flagged items | Share of reference items whose event reached band ≥ report in the system, at any time before or within 2 h after the reference time |
| Coverage-adjusted recall | The same, counting only items whose underlying story existed in at least one collected source. Shows ranking quality apart from source coverage (the desk has AP/Reuters; the round-2 system has public feeds only) |
| Time-to-alert | System first band ≥ report time minus reference time (variant A: publication time is a late proxy for desk awareness, so the comparison favours the system and is labelled so; variant B: registration time). Also reported against the earliest `first_seen_utc` of any member, to separate collection latency from ranking |
| False-alert load | System flash and report alerts per 8-hour shift that match no reference item and that the blind adjudicator rules not worth registering |
| Monitor effort | Queue rows at band ≥ review per shift (the rows a person would have to read) |

All metrics come with bootstrap 95% confidence intervals over days (n = 7 days, 21 shifts). Expected volume, INFERRED
from the "fewer than 10 of 700–800" desk figure (`01_INDUSTRY…`): roughly 30–70 reference items per day, 200–500 per week.

### 8.4 Decision rule (fixed before the week)

| Outcome | Condition |
|---|---|
| Useful as a second pair of eyes | Coverage-adjusted recall ≥ 0.80 **and** false-alert load ≤ 5 per shift |
| Useful for handoff and morning briefing only | Coverage-adjusted recall ≥ 0.80 but false-alert load > 5 per shift |
| Not useful yet | Coverage-adjusted recall < 0.80; the miss-cause table says what to fix |

The result is reported whichever way it falls, with the miss-cause table. The comparison does not claim the system
replaces the monitor; the 외신 seat's video half is out of scope (deliverable 09).

## 9. Operational metrics (in production)

| Metric | Definition | Source | Alert when |
|---|---|---|---|
| Source health | Fetch success rate per feed (24 h); open incidents by kind; time from first failure to incident open | `fetch_run`, `incident` | Success < 90% for a feed; any incident open > 6 h |
| Collection completeness | Items per hour per feed vs its 7-day median; polls with overlap 0; GDELT gaps; inbox files `gone` before ingest | `fetch_run`, `inbox_ledger` | Below 30% of median for 3 h; any overlap-0 poll; any `gone` before ingest |
| End-to-end latency | p50/p95 of publisher time → first seen → visible in queue; inbox file mtime → visible | `article`, `feed_entry` | p95 above NFR-01 for 1 h |
| Missed-story rate | Weekly: 20 major international stories from an outside reference (for example GDELT's top events or the reference record of §8) checked for presence at band ≥ review | Manual weekly audit, `eval/shadow` tools | More than 2 of 20 missed for coverage-adjusted reasons |
| Alert precision | Share of alerts acknowledged vs dismissed; alerts per shift | `alert`, `editorial_assessment` | Dismissed > 50% over a week |
| AI health (when on) | Enrichment backlog, validation failure rate, review-queue size, injection flag rate, spend vs cap | `ai_interpretation`, `spend_day` | Backlog > 1 h; failure rate > 5%; spend ≥ 2× expected |
| Integrity | Last good backup age; DB size; free disk | `/healthz` | Backup > 26 h old; free disk < 2× DB size |

## 10. Limits of this plan

- **Keyboard operation** (FR-18c) is checked as wiring in the rendered HTML (TS-FR18c), not as behaviour. A browser test
  tool (for example Playwright as a dev-only dependency) would close this; deliverable 10 lists Playwright only as a
  deferred scraping tool, so adding it is an open question.
- **Symlink refusal** (TS-FR28d) may be skipped on Windows without developer mode; the Ubuntu CI job must run it.
- **Linux** install and service files are proven only in CI; the Dockerfile is untested.
- **AI quality numbers** in phase 1 come from small samples (11 articles); the floors in §6 that depend on them are
  provisional until E3, E5 and E7 exist.
- **Variant A** of the human comparison measures against a published record, which lags desk awareness and reflects
  editorial choices beyond monitoring. Variant B is the real test and needs a partner.

## 11. Reuse of phase-1 harnesses

| Harness | Reused for |
|---|---|
| [`experiments/deduplication/dedup_experiment.py`](../experiments/deduplication/dedup_experiment.py) (exact-Jaccard reference, MinHash scoring) | TS-FR08a, E1 |
| [`experiments/deduplication/syndication_breakdown.py`](../experiments/deduplication/syndication_breakdown.py) | TS-FR09a/b fixtures |
| private experiment data (not published), `cluster_variants.py` (pair and B³ metrics, TF-IDF and embedding variants) | TS-FR10a, TS-FR10b, E2 |
| [`experiments/korean-fts/fts_experiment.py`](../experiments/korean-fts/fts_experiment.py) (queries, substring truth, method D) | TS-FR20a/b, E4 |
| [`experiments/event-clustering/spike-detection/spike_detect.py`](../experiments/event-clustering/spike-detection/spike_detect.py) | TS-FR17c |
| private experiment data (not published) (v2 schema, hardened prompt, semantic validators, content-hash cache) | T-49, TS-FR12a-live, E5 |
| [`experiments/ai-processing/analyze.py`](../experiments/ai-processing/analyze.py), `repeat_triage.py` (grounding, noise) | E3 (LLM band noise), E5 |
| [`experiments/ai-processing/prompts/attacks.json`](../experiments/ai-processing/prompts/attacks.json) | TS-FR14a, TS-FR14b, E7 |
| [`experiments/source-collection/probe_sources.py`](../experiments/source-collection/probe_sources.py) (RFC 9309 matcher) | T-12, TS-ROB-01 |
