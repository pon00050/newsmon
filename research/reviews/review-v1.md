# REVIEW_V1 · Independent adversarial review of deliverables 03–14 (V1, 2026-11-25)

> **Status: Historical decision.** Independent review of the research deliverables; its defects were fixed in the documents (decision log P-010).
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

> **Status (2026-11-25, Round 3):** HISTORICAL. Its findings were resolved in [`decision-log.md`](../decision-log.md) P-010.

Scope: a private review brief, items 1–7, time-boxed to about 15 minutes, with blocker and major defects first.
Reviewer did not write any of the reviewed files. Nothing outside this file was changed. API spend: $0. Two AP pages were
fetched with curl (one request each, project UA).

## 0. Status of the five gaps S2 already found (not re-reported)

| S2 gap | Fixed in the source deliverable? | Compensated in the backlog? |
|---|---|---|
| (1) No `feed_entry` table for FR-07(a) | **No.** 11 §5 DDL still has no `feed_entry` | Yes: G-1, T-07 adds it |
| (2) `workspace_id` missing on `spend_day` and child tables | **No.** 11 §5 lines 279, 364, 384 unchanged | Yes: G-2, T-07 and T-61 (children scoped by FK) |
| (3) PyYAML missing from 10 | **No.** Absent from 10 and 11 §7 | Yes: G-3, T-02 pins it at build |
| (4) 14-day backups vs 7-day `mock_wire_gated` retention | **No.** 11 §8 still says "the last 14 dailies are kept" | Yes: G-4, T-54 caps rotation and T-25 receipt lists backups |
| (5) Injection regex must run in O1 for FR-21(c) | **No.** 12 FR-14 still says "MUST (when enabled)" | Yes: G-5, T-45 in W1 says "runs in every mode" |

S2 also logged G-6: FR-14(b)'s "44 clean hardened fixtures" are 11 distinct texts. I confirmed this from `raw/`: 22
extract + 22 triage hardened clean calls over 11 articles, and 0 of 44 clean calls had the model flag set. Not re-reported.

**Required fix (one line):** amend 10, 11 §5/§8 and 12 FR-14, or add a note at the top of 11 and 12 saying that 13 §6
G-1…G-6 supersede them. A coding session that builds from 11 §5 instead of T-07 will rebuild all five defects.

## 1. Defects

| id | severity | file:location | defect | evidence | required fix |
|---|---|---|---|---|---|
| V1-01 | **major** | 12 §2 "Queue display" row and FR-06, FR-12; 13 T-22 (`TS-FR06c-unit`) | **AI-derived fields are not governed by the `display` flag.** Enrichment runs on `ai_processing=unknown` sources (title + feed summary, FR-12(b)) and returns "key quotes translated, **with the originals kept**". These are verbatim source text, shown in the queue for sources whose `display=headline` (25 of 27 public seed rows). The only display test asserts that the *whole* feed-summary string is absent, so a verbatim quote taken from the summary passes it. The Korean "summary" of a 1–2 sentence feed summary is in practice a translation. Legal matrix row a5 (translate) is **C** in internal use and **R** for published translations of protected text. Neither 12 nor 13 decides whether this counts as an "own-words summary" (DR-3) or as a translation | 12 lines 56, 211–217, 285–296; 08 §6 rows a3 and a5, DR-3; 13 lines 616–631 | Make `DisplayPolicy` cover the `ai.*` fields as well as source fields. For `display < snippet`, suppress `quote_original` and every verbatim quote. Add a test asserting that no source substring of 20 or more characters appears in any surface for a headline-only item. Gate the Korean summary of a headline-only source on `permitted_ops ∋ translate` or `summarise`, and record the project owner's ruling on whether it counts as "own words" |
| V1-02 | **major** | 12 FR-22 (Draft: Sonnet); 13 T-51; 14 | **The AI digest draft is not licence-gated per item.** Digest selection is by rules, so a `mock_wire_gated` flash item (urgency 1, which FR-21(a) requires to fire) can enter the handoff edition. The draft is one multi-item Sonnet call. No requirement or test excludes or redacts items with `external_ai_allowed=false` or without the needed op in `permitted_ops`. FR-15(d) and `TS-FR15d` check only per-item enrichment and triage through the router. T-51 depends on T-47 but declares no gating test | 12 lines 444–455; 13 lines 1081–1095 (tests cover only citations, label and rewrite); 13 T-47 covers FR-15d for per-item calls only | Add FR-22(e): the draft prompt is built item by item through `LicenceGate`. A gated item enters as `[id, headline withheld]`, or is listed only by the template. Add `TS-FR22e` (AI stub): a digest that contains a `mock_wire_gated` item sends 0 bytes of its text to the hosted provider (stub call log). Apply the same rule to MCP `get_briefing` when the briefing is AI-drafted |
| V1-03 | minor | 12 §6 seed rows `yna_news`, `yna_intl`, `yna_nk` | `external_ai_allowed=true` contradicts 08 §13.4: "treat 연합뉴스 as … AI restriction likely, and default `external_ai_allowed=false`". Yonhap footers appear to carry an AI-use prohibition (U). The rows are P-only, so the risk is low, but the seed contradicts the legal deliverable and gives no reason | 08 lines 399–401; 12 line 615 | Set the flag to `false` for the three rows (they then run in O1), or record an explicit project-owner decision in DECISION_LOG |
| V1-04 | minor | 08 DR-17 vs 12 FR-27 and ADR-010 §8 | DR-17 says "mock and sample data carry `synthetic=true` and **bypass licence logic**". ADR-010 and 12 correctly attest `mock_wire_gated` with the most restrictive flags so that it *demonstrates* the gate. A session that follows DR-17 literally could make `synthetic` skip the gate, which makes FR-15(d) and FR-24(b) meaningless | 08 line 408; ADR-010 line 229; 12 line 515 | State in 12 FR-27: "`synthetic` is provenance only and never alters `LicenceGate` or `DisplayPolicy`". Add a test. Note the override against DR-17 |
| V1-05 | minor | 11 §5 `audit_log`; 12 FR-26 | DR-20 (the licence audit log) asks for the derivative produced, the retention deadline, the credential **id**, the operation type (classify, summarise, translate) and an **exportable licence-audit report**. `audit_log` has only generic `target`, `licence_flags` and `detail` columns, and no export of this kind is specified. DR-16 `commercial_model` appears nowhere in 11, 12 or 13. That is acceptable for a single-tenant Model-B build, but it is undocumented | 08 lines 407, 411; 11 lines 381–383; 12 FR-26 | Add `derivative_kind`, `retention_until` and `credential_ref` to AI and fetch audit rows, plus `newsmon audit export --source`. Note DR-16 as satisfied by construction (single tenant, Model B) |
| V1-06 | minor | 12 FR-21(a), AC-O1-04 vs FR-28 and ADR-010 §5 | The 60 s alert criterion conflicts with the default 30 s inbox scan. A file must be seen stable across two scans before it is ingested, so the worst case is about 60 s before the pipeline even starts | ADR-010 line 117; 12 lines 435, 532 | Fix the scan interval in the test (for example 5 s), or state the criterion as "≤ 2 scan intervals + 30 s" |
| V1-07 | minor | 12 §2 Event-grouping row vs FR-10 | §2 quotes "O1 pair F1 0.37", which is the θ 0.15 result. FR-10 fixes θ 0.2 (R6: P 0.872, R 0.208, F1 0.336). The 0.80 precision floor is measured on the same gold set the thresholds were tuned on (R6 F-4). The added gazetteer co-occurrence linking is untested and can only lower that precision | [`experiments/event-clustering/results.md`](../experiments/event-clustering/results.md) table and F-4; 12 lines 52, 260–267 | Quote 0.336 / P 0.872. Say that AC-O1-05 runs on the tuning set. Run the precision test both with and without gazetteer linking |
| V1-08 | minor | ADR-010; 11 | P-007 requires Model A and Model B to be evaluated separately in ADR-010 and 11. Both files have 0 mentions of "Model A". The separation exists only in 02 §8.2, 08 §13 and ADR-003. This does not mislead the build, but it is a gap against the project brief | `grep -c "Model A"`: ADR-010 0, 11 0 | Add a short "Model A delta" section to ADR-010: provider-owned credentials, shared collection, the redistribution licence and the DR-29 gate, with what the code would have to change |
| V1-09 | minor | 12 §3; 13 §2 | The MVP is coherent but not minimal: 64 tasks, about 71 h on the critical path. It includes the O2/O3 AI tasks (T-46…T-52), the MCP server, multi-user auth with CSRF, an untested Dockerfile, the eval harness and the shadow-week kit. Nothing the supplement said to defer has crept in: billing, SSO, multi-tenancy and licence keys are all excluded (13 §1) | 13 lines 30–31, 37–60 | Declare T-59 (O1 acceptance) as the MVP-1 release gate. Treat T-46…T-53 and T-60…T-64 as slice 2, without changing their content |

No blocker defects were found.

## 2. Findings per brief item

1. **Evidence integrity (28 claims sampled, 0 overstated tags found).** The TESTED claims were checked against the files in
   `03_experiments`. R7: costs $0.0013 and $0.0275 per article; grounding 105/107; v1 failures 2/11 and 1/11, v2 14/14;
   0/24 hijacks; 48/48 attacked calls flagged and 0/44 clean calls flagged (I recounted both from `raw/*.json`); A2 +22.6;
   triage noise 35–62; mean model difference 7.8. R6: TF-IDF 0.371 / B³ 0.837 at θ 0.15 and recall 0.208 at θ 0.2;
   (b3) 0.776 / 0.901 / 0.360; embeddings $0.002 for 826 items; 571 items in 24 h from 23 feeds. R4/FTS: KO unicode61
   0.684 and ZH 0.088, bigram 1.000, 0 nonsense hits. Dedup: MinHash at t 0.9 and 0.5, SimHash recall 0.449 (the "45%").
   Seed: 27 public rows and 8 P rows. `probe_summary.csv` gives status 200 for bbc_world, dw_en_all, npr_news,
   bbc_zh_simp and dw_zh_all; they were found through third-party directories, not guessed URLs. VERIFIED claims:
   AP Media Agent's 72 h look-back and its NewsML-G2/NITF formats were re-fetched at developer.ap.org and match E-A1
   and E-A9. The licence tags in 10 and 11 §7 (FastAPI D, htmx V, tldextract I) are honest.
2. **Consistency.** Every FR-01…31 appears in both 12 and 13. Apart from the known S2 gaps (which 13 compensates for),
   the components, sources and scope agree across 10, 11, 12 and 13. No recommended dependency conflicts with 03's
   licence or maintenance verdicts. No row in 10 needs local inference; kiwipiepy is deferred and excluded.
3. **Legal fit.** Full-text storage, body fetch, the default display, redistribution, labelling (DR-8), takedown, YouTube
   and AGPL handling all follow 08. The exceptions are V1-01 (AI-derived verbatim quotes and translations), V1-03 and
   V1-05.
4. **Feasibility.** The acceptance criteria are numeric or assertion-based. Every task completion is a single command
   that must exit 0. V1-06 and V1-07 are the only weak measurements. On scope, see V1-09.
5. **Deployment flexibility.** ADR-009 classifies all 16 supplement-01 topics. The expensive-to-retrofit items are decided
   now: the `workspace_id` seam (incomplete in 11, so known gap 2 applies), the `SecretStore` interface, and no AGPL code
   in the core. No DEFER item is in the MVP.
6. **Customer-owned licensing.** The MVP runs on local files and mock wire input through one connector contract, and it
   has no paid-wire prerequisite (FR-27–FR-30, ADR-010). `external_ai_allowed` gates enrichment, triage, embeddings and
   MCP, but **not the AI digest draft** (V1-02). The AP Media Agent claims trace to fetched AP pages (verified). The
   Arirang claim is honestly recorded as not located (02 §8.1, ADR-003, 12 OQ-11). Model A is missing from ADR-010 and
   11 (V1-08).
7. **Missed alternatives.** None found. Taranis AI (K-A), `reader` and `datasette-mcp` were each dismissed with reasons
   and reversal triggers. RSSHub and changedetection.io were kept as optional adapters.

## 3. Approved list (can stand as they are)

02, 03, 04, 05, 06, 07, 09, ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009.

These need edits:

| Deliverable | Edits needed |
|---|---|
| 08 | V1-04 wording |
| 10 | Known gap 3 |
| 11 | Known gaps 1, 2 and 4, plus V1-05 |
| 12 | V1-01, V1-02, V1-03, V1-06 and V1-07, plus known gap 5 |
| ADR-010 | V1-08 |
| 13 and 14 | Add the V1-01 and V1-02 tests |
