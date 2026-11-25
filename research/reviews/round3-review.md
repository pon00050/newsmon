# Round 3 review: consolidation and simplification (2026-11-25)

> **Status: Implemented (Release A + A.1).** Consolidation review of the implemented Release A + A.1.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Scope: an independent review of Release A + A.1 of `newsmon` and its documents. No new features beyond what a
finding required, no new research, no paid API calls, no local model inference. The live database was not modified
(SHA-256 prefix `b105e54235d3d385` before and after).

Recovery point taken before any change: a private checkpoint archive.

## A. Findings and what was done

### Verdict

The implementation is small (about 5,300 lines of source, one process, one SQLite file) and its structure is sound.
The review found no reason to restructure it. It did find eleven real defects in licensing and failure handling, all
now fixed with a regression test each, one operational crash, and a set of documents that still described the full
MVP as if it were the current target. The largest remaining simplifications need the owner's decision (section E).

### Defects fixed

Each has a test in `tests/integration/test_round3_fixes.py` (17 tests) unless noted.

| # | Problem | Fix |
|---|---|---|
| 1 | A wire version that added a restriction without changing the text, or an older version arriving late with a restriction, was ignored. The full body stayed on display. | Any arriving version's restriction is recorded before the early returns (`repo/articles.py`). |
| 2 | `withheld` items and items under a future embargo were ingested as ordinary items. Embargo fields were not read at all. | Both become restrictions: headline-only display, no AI. Embargo is read from NewsML-G2, NITF and ninjs. |
| 3 | A restricted or withdrawn item could still be sent to the AI provider (automatically or by hand). | `route()` refuses both, on every path. |
| 4 | AI text made before a restriction arrived stayed visible after it. Found by the verification pass. | A restricted item shows no AI text. |
| 5 | A live copy arriving after a withdrawal became a hidden duplicate of the withdrawn item. | A withdrawn item is never chosen as a duplicate's primary. |
| 6 | One malformed inbox file (wrong-typed field, or JSON nested too deep to classify) aborted the whole inbox scan, on every cycle. | Any failure in classifying or parsing a file quarantines that file once; the scan continues. |
| 7 | Quarantine reasons and logs could quote source text (parser exception text, field values, the injection filter's matches). They appear on the 소스 상태 page. | Reasons carry a fixed message or the exception type only. |
| 8 | An RSS entry with neither id nor link raised a database error on every poll after the first. | It is found again by its derived identity. |
| 9 | The rule that AI text may not repeat 20 characters of a headline-only source was defeated by changing case, spacing or punctuation. | Comparison is on normalised letters and digits. |
| 10 | The XML entity guard for feeds missed UTF-32, and encodings such as EBCDIC or UTF-7 in which the declaration is spelt with other bytes. | UTF-32 is covered; feeds declaring an encoding outside the expected list are refused. |
| 11 | `newsmon status` crashed with `UnicodeEncodeError` when its output was redirected on Windows. Found during the operational check. | Redirected output is written as UTF-8. |

Also changed: sidecar media files are hashed in chunks instead of being read whole into memory; the RSS path now
quarantines on any parser exception, as the inbox path does.

### One capability added, because a known limit asked for it

AI assessments made under an earlier profile, model or prompt were invisible and could only be refreshed one item
at a time. The AI page now counts them, and `newsmon enrich --stale --limit N` reassesses them on request, under
the same daily cap. Counting is free and sends nothing. Nothing is ever reassessed automatically.

### Simplification done

- Test harness: two fixed setup costs (TLS context creation, MinHash parameter search) are computed once per run.
  Gate time fell from 152 s to about 94 s with 17 more tests.
- Removed unused definitions: the `SearchIndex`, `Notifier` and `AuthProvider` ports with their data classes, two
  unused enums and one unused helper (about 55 lines). No file was deleted.
- `latest_for_articles` filters in SQL instead of loading every assessment.
- Documents: the root `README.md` is now the single entry point and states which document wins when two disagree.
  Four research-round documents carry a HISTORICAL or EXECUTED banner. The package description no longer claims
  event grouping, alerts and digests.

### Findings accepted but not acted on

| Finding | Why not |
|---|---|
| Every cycle re-ranks every stored article (about 0.6 s per 1,000). | Scores decay with age, so skipping unchanged articles would change results. Recorded as the first scaling limit in the README. |
| 17 database tables belong to deferred features and are empty. | Removing them is a schema migration on the live database. Owner decision (E1). |
| `datasketch` pulls in numpy and scipy for one MinHash index. | Replacing it changes duplicate detection and needs its own equivalence test. Owner decision (E2). |
| Empty packages `delivery/`, `mcp/`; `adapters/null_ai.py` used only by tests. | File deletions. Owner decision (E3). |
| Several tests assert little (for example, that a call does not raise). | Listed by the test reviewer; none hides a known defect. Left as is. |
| `python -m newsmon.cli <command>` registers no commands; only the `newsmon` script works. | Cosmetic; the documented entry point works. |

### Findings rejected

- "Re-rank only when needed", for the reason above.
- Treating public feeds as cleared for AI processing to make the AI path simpler. A feed being public is not a
  licence. The shipped configuration still sends nothing from public feeds.

### Known limits that remain (also in the application README)

- Restrictions do not lift. An embargo that has passed, or a `withheld` item later released, stays headline-only
  and unassessed. A restricted item also stays findable by words in its body through search.
- A restricted primary hides a later unrestricted copy from another source as its duplicate. This over-restricts;
  it does not leak.
- An embargo time without a timezone is read as UTC.
- The 20-character rule can still be evaded by deliberately crafted model output (look-alike letters).

### Delegation record

| Task | Model | Mode | Tokens | Outcome |
|---|---|---|---|---|
| File, dependency and schema inventory | Haiku | read-only | 94k | accepted; basis of the unused-table and dead-code lists |
| Security and licensing review | Opus | read-only, probes on throwaway instances | 194k | 9 findings, all reproduced, all fixed |
| Test-suite analysis | Sonnet | read-only | 217k | harness speed-up accepted; weak-test list recorded |
| Architecture review | Opus | read-only | 240k | "no restructuring" accepted; re-rank proposal rejected on evidence |
| Documentation review | Sonnet | read-only | 195k | authority order and banners accepted |
| Verification of the fixes | Opus | read-only, did not write the fixes | 148k | 6 adequate, 4 incomplete; all 4 then fixed (rows 4, 6, 7, 10) |

All code changes were made by the orchestrator, one at a time. Subagent total: about 1.09 million tokens. The
orchestrator's own tokens and the dollar cost were not metered in this round. One disagreement arose (re-rank
frequency) and was settled by reading `rules/engine.py`: the score depends on the current time.

## B. Before and after

| Measure | Before | After |
|---|---|---|
| Gate result | 320 passed, 2 skipped | 337 passed, 2 skipped |
| Gate run time | 152.5 s | 93.8 s |
| Source lines (`src/`, Python) | 5,262 | 5,312 |
| Test lines (`tests/`, Python) | 4,392 | 4,702 |
| Release A requirements covered (`tools/req_coverage.py`) | 14/14 | 14/14 |
| Runtime dependencies | unchanged | unchanged |
| Database schema | unchanged | unchanged |
| Live database | 5.4 MB | unchanged, byte for byte |
| Disk | | +13.3 MB (the recovery checkpoint) |
| Entry-point documents | several, none ranked | one (`README.md`), with an authority order |
| Operational steps | | unchanged; one optional command added (`enrich --stale`) |
| AI calls per article | 1 | 1 (unchanged); restricted and withdrawn items now cost 0 |

Source grew by 50 lines: the fixes added more than the dead-code removal took out. Not measured: memory use, CPU
per cycle beyond the re-rank timing, and collection throughput against live feeds.

## C. Current guide

`README.md` at the project root. To run the application: the application `README.md`.

## D. Verification

- **Gate:** `uv run pytest -q -m "not live and not slow" -p no:cacheprovider` → 337 passed, 0 failed, 2 skipped
  (both are symlink tests that Windows cannot run without developer mode).
- **Existing tests changed:** five tests sent a restricted fixture item or a withdrawn item to the AI stub, which
  the new rule correctly refuses. They now use unrestricted, live items. Their purpose is unchanged and no
  assertion was loosened.
- **Progress report:** the generated `PROGRESS.md` was regenerated from the final run; every full or partial task reports PASS.
- **Independent verification:** a reviewer that did not write the fixes attacked each one on throwaway instances.
  The four gaps it found were fixed and tested. Those four follow-up fixes were not themselves re-verified by a
  second party; they are covered by their tests only.
- **Operational check, on a copy of the live database:** `status`, `search`, `rerank` (1,174 articles) and
  `enrich --stale` (0 stale; AI off) all ran. This is how the `status` crash was found.
- **Not performed:** `newsmon serve` in a browser; a live collection against real feeds; any live AI call; Linux.
- **Spend:** no paid API calls. Development time was not instrumented.

## E. Decisions for the owner

| # | Issue | Options | Recommendation |
|---|---|---|---|
| E1 | 17 empty tables for deferred features | (a) keep; (b) drop in a migration | Keep until Release B is decided. They cost nothing at run time, and dropping them means re-adding them later. |
| E2 | `datasketch` brings numpy and scipy | (a) keep; (b) replace with a small in-house MinHash | Keep. Revisit only if install size or start-up time becomes a problem. |
| E3 | Delete `src/newsmon/delivery/`, `src/newsmon/mcp/`, `adapters/null_ai.py` and the two stray `data/*collect_log.jsonl` files | (a) delete; (b) keep | Delete the three source items (the checkpoint holds them). Look at the two log files before deleting. Nothing was deleted without your word. |
| E4 | Restrictions never lift after an embargo passes | (a) keep; (b) re-evaluate time-based restrictions each cycle | (b), before any real wire feed is connected. It is a small change, but it alters what is displayed, so it is yours to approve. |
| E5 | Wire `usageterms`, rights notices and editor's notes are stored but not interpreted | (a) leave; (b) define a vocabulary per customer contract | Leave until a real contract exists. Do not generalise from one example. |
| E6 | The meaning of `third_party_processors_allowed` versus `external_ai_allowed` | define, or remove one | Needs the licence text of an actual source. Unresolved. |
| E7 | `status` and `search` apply migrations and reload configuration | (a) keep; (b) make them read-only | (b) when convenient. Low risk today with one operator. |
| E8 | ADRs 001–010 are all still marked PROPOSED | flip those that were built to ACCEPTED | Yours to decide. [`decision-log.md`](../decision-log.md) now states how much of each is built. |
| E9 | Licence flags are fixed on an article at ingest | (a) keep; (b) add a command to re-apply a source's current flags | Keep. A tightening that must reach old articles is rare and can be done by hand. |
