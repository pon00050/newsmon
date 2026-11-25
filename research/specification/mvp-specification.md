# 12 · MVP specification (S1, 2026-11-25)

> **Status: Design proposal (not built).** Deliverable 12. This document describes the FULL MVP. Most of it is not built: Release A + A.1 implements only a subset (collection of authorised feeds and wire files, normalisation, deduplication, rule ranking, search, a local queue, and optional AI assessment). See the [decision log](../decision-log.md) for what is built.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Status:** PROPOSED. This document is the single definition of the MVP. Decisions: [`architecture/adr/`](../architecture/adr).
Architecture: [`architecture/recommended-architecture.md`](../architecture/recommended-architecture.md). Interfaces: [`specification/interface-spec.md`](interface-spec.md).
Traceability: [`specification/requirements-traceability-matrix.md`](requirements-traceability-matrix.md) and `traceability.csv`.

**Working name:** `newsmon`.

**Round-1 review amendments (2026-11-25, orchestrator, from [`reviews/review-v1.md`](../reviews/review-v1.md)).** These are normative and
are applied in place below:
- FR-06(f): AI fields obey `display` (V1-01).
- FR-22(e): AI digest drafts are licence-gated per item (V1-02).
- FR-27(d): `synthetic` is provenance only (V1-04).
- FR-14 detection runs in every mode (known gap 5).
- Yonhap seed rows set to `external_ai_allowed=false` (V1-03).
- Inbox scan default of 10 s (V1-06).
- Corrected O1 clustering numbers (V1-07).
- Backup retention is capped by the shortest source `retention_days` (known gap 4).
- MVP-1 release gate = T-59, the O1 acceptance task (V1-09).

**Release slices (V1-09).**
- **MVP-1** is everything needed for O1 acceptance: backlog T-01…T-45, T-53 and T-54…T-59. This is exactly T-59's
  dependency closure, computed from `backlog.csv` on 2026-11-25.
- **Slice 2** adds the optional AI layer (T-46…T-52) and the T-60…T-64 hardening and eval kit.

The requirements themselves are unchanged. Only the order of delivery is.

**Priorities:**
- **MUST**: required for the MVP to be accepted.
- **SHOULD**: in the MVP unless time runs out.
- No COULD items. Anything else is excluded (§4).

## 1. Target user and use case (D3, ADR-003)

**User.** One foreign-news (외신) desk monitor, or the editor beside them, in one organisation. In round 2 the researcher
acts as that user in `use_context=private`.

**Commercial model: Model B.** The product is software that processes content the customer already licenses (AP/APTN,
Reuters, 연합뉴스) together with free public sources. The provider acquires and distributes no content. Whether Model B
works for a given customer is decided by what that customer's contract says. The customer enters those terms as source
flags at onboarding.

**Why this use case:**
- It is the seat least served by commercial products. A clipping service would reproduce what AISURFER and
  스크랩마스터 already sell, under licences the provider would have to buy itself (`02_COMMERCIAL…` §1, §5, §8.2;
  `08_LEGAL…` §0, §13.0).
- Its text half is reachable and testable now, on public feeds and on synthetic wire files (`04_INFORMATION_SOURCE…` §1;
  ADR-010).
- The desk needs a persistent registration plus a separate notice, and wants precision over recall
  (`01_INDUSTRY…` F-A-02, F-A-03).

**Use case.**
1. Watch EN/KO/ZH foreign-news text from public feeds and from the customer's wire files.
2. See one deduplicated, event-grouped, ranked queue.
3. Get a notice for flash items.
4. Register important items with a note.
5. Search the archive.
6. Send a reviewed shift-handoff or morning briefing.

**Not served.** The video half of the seat (footage monitoring, ingest, archive, video feed faults) is out of scope.
Deliverable 09 states this per duty.

## 2. Operating modes (O1–O3, plus O4 via MCP; ADR-006)

The MVP is **fully functional in O1, with no AI provider configured**. AI is switched on per capability in
`settings.yaml` → `ai.capabilities.{triage, enrich, embed, digest_draft, query_rewrite}`, and per source through the
licence flags `ai_processing`, `permitted_ops` and `external_ai_allowed`. There is no model training or fine-tuning
anywhere.

| Capability | O1 fully deterministic | O2 adds (single LLM calls) | O3 adds (embeddings) | O4 (external agent via MCP) |
|---|---|---|---|---|
| Collection, normalisation, dedup, feed health | complete | — | — | — |
| Event grouping | Per-language TF-IDF incremental clustering, plus gazetteer-entity co-occurrence linking within 48 h, plus manual merge/split | — | Embedding clustering. Measured pair F1 0.78 vs O1 0.34 at θ 0.2 (P 0.87, R 0.21; 0.37 is the θ 0.15 result), cross-lingual recall 0.36 vs 0. All measured on the tuning set, so optimistic. Gazetteer linking is untested | — |
| Relevance and priority | Weighted rules: watch terms, entities, countries, source weight, independent sources, urgency, spike | LLM triage band as a second opinion. Can raise an item to `report`, never to `flash` | — | — |
| Queue display | Original headline, plus feed summary where `display ≥ snippet`. Language tag | Korean headline and 3-sentence summary, who/what/where/when, attributed claims, key quotes translated with the original kept (labelled AI) | — | — |
| Search | BM25 over bigram FTS5, plus deterministic alias expansion from the gazetteer | LLM query rewrite into KO/EN/ZH terms | — | The user's own agent queries the read-only tools |
| Digest | Template: top events by band, independent sources and recency. Original titles and links | Sonnet prose draft with cited article ids | — | — |
| Alerts | Rules only | — | — | — |
| Cost | $0 API | ≈ $1–5/day at 1,000–3,000 items | + ≈ $0.01/day | Paid by the user's client |

**Where O1 is weaker, stated plainly:**
- O1 gives no Korean summary or translation of English or Chinese text. The monitor reads the original.
- O1 does no cross-lingual event linking beyond shared gazetteer entities.
- O1 clusters under-merge, at recall about 0.21, so the queue has more rows per real event.
- O1 relevance covers only what the profile names.
- O1 briefings are lists of titles and links, not prose.

## 3. Included capabilities (summary)

| Area | What is included |
|---|---|
| Collection | Public RSS/Atom and keyless APIs, through one connector contract |
| Customer wire files | A watched inbox directory for wire files (NewsML-G2, NITF, ninjs, plain text), with synthetic fixtures |
| Licence gating | Customer-set licence flags with attestation |
| Dedup | URL, hash and MinHash dedup, plus revisions |
| Events | Event grouping |
| Ranking | Rules-based ranking |
| AI | Optional LLM enrichment and embeddings |
| Desk surfaces | Editorial queue with verdicts; event and item detail with provenance; KO/ZH/EN search |
| Delivery | Flash and spike alerts; feed-health incidents; scheduled and handoff digests with human review |
| Configuration | Profile editor (YAML and form) |
| Interfaces | Read-only JSON API; read-only MCP server (SHOULD) |
| Operations | Audit log; export/import; backup/restore; single-tenant deployment on Windows or Linux without Docker |

## 4. Explicit exclusions

| Excluded | Reason / where decided |
|---|---|
| Video, audio and footage processing (ingest, transcoding, scene detection, OCR, ASR, thumbnails) and video feed-health monitoring | ADR-007. Media files are recorded as references only |
| YouTube (channel RSS or Data API) | robots.txt disallow; no key (ADR-002) |
| AP Media API and Reuters Connect live connectors | Designed, deferred until a customer provides a contract and key (ADR-010). Paid wire access is not a prerequisite |
| NRCS/MAM/CMS integration (MOS, BXF, webhooks); NRCS file export | Deferred (ADR-010 §7). File export is post-MVP slice 1 |
| Client clipping / redistribution service (Model A) | ADR-003; DR-29 |
| Multi-tenancy, SSO, billing, licence keys/entitlements, usage-based metering, shared collection | ADR-009 DEFER items |
| PostgreSQL, search servers, vector index (sqlite-vec) | ADR-004 |
| RAG, runtime agents, multi-agent, MCP write tools, remote MCP over HTTP | ADR-006, ADR-008 |
| Model training or fine-tuning of any kind | DR-7; project-owner guidance |
| Local model inference, including kiwipiepy as a dependency | Workspace no-local-inference policy; ADR-004 |
| Contradiction detection, numeric-claim diff, novelty scoring, sentiment | ADR-005 |
| Dedicated MT APIs (DeepL, Papago, Google) | BLOCKED-no-key (`06_AI…` §3) |
| Messenger channels (KakaoTalk/Telegram/Slack), webhooks, RSS output | ADR-008 (apprise later) |
| Social sources (Bluesky, Mastodon, X), Naver/Daum news, BIGKinds, SBS, Reuters/AP websites, MBC, state.gov | ADR-002 |
| Browser automation, generated feeds (RSSHub), page change detection (changedetection.io) | ADR-001: adapters designed, off |
| Maps, topic dashboards, source-comparison views | ADR-008 |

## 5. Functional requirements and acceptance criteria

Acceptance criteria are written so that S2 can turn each one into an automated test. Test conditions:

- **"Fixture set"** means recorded public-feed responses served by a local fixture HTTP server, plus the synthetic wire
  inbox fixtures of ADR-010 §8. No network is used.
- **"AI stub"** means a deterministic fake provider.
- Live-provider checks are marked [live].

### 5.1 Sources and collection

**FR-01 · Source registry as data, with licence flags · MUST**

The registry is loaded from `config/sources.yaml` into `source` rows. It carries the DR-1 flags plus
`external_ai_allowed`, `permitted_ops`, `allowed_contexts`, `third_party_processors_allowed`, and the DR-17 attestation
fields.

- Unknown values default to: `storage=metadata`, `display=headline`, `ai_processing=unknown`, `external_ai_allowed=false`
  (seed sets true for public floor sources), `permitted_ops=[]`, `redistribution=none`, `training=no`.
- A source whose `allowed_contexts` excludes the workspace's `use_context` is inactive.

*Acceptance criteria:*
- (a) Loading the 27-row public seed plus 2 mock wire rows creates 29 rows. Every flag column is non-null.
- (b) A row with no flags gets exactly the defaults above.
- (c) In `use_context=internal`, the sources marked `private` only (Guardian, CNA SG, Yonhap ×3, Kyunghyang, CNA TW ×2)
  are inactive, and no fetch is attempted for them.
- (d) `training` cannot be set to anything but `no`. The CHECK fails on insert.

**FR-02 · Feed and API connectors · MUST**

The connectors poll on a per-feed interval (minimum 300 s). They use:
- conditional GET (ETag / Last-Modified);
- a configured descriptive User-Agent;
- an RFC 9309 robots.txt check (re-checked daily per host);
- one in-flight request per host;
- a refusal at connect time of loopback, private, link-local and metadata addresses, including after redirects.

*Acceptance criteria (fixture server):*
- (a) The second poll sends `If-None-Match` and `If-Modified-Since` when validators were stored. A 304 response yields
  `status=not_modified` and 0 new rows.
- (b) A path disallowed by `Disallow: /r?` style rules is never requested. The fixture server log shows 0 hits.
- (c) Every request carries the configured UA string exactly.
- (d) Fetches to `127.0.0.1`, `10.0.0.5`, `169.254.169.254`, and a public host that 302-redirects to `127.0.0.1`, all end
  with `error_class=ssrf_blocked`, and the fixture server sees no connection on the private address.
- (e) Two feeds on one host are never fetched concurrently. Measured from fixture server timestamps.

**FR-03 · Fetch run recording and retry policy · MUST**

Every poll writes one `fetch_run` row with `status`, `http_status`, `entries` and `error_class`.
- Timeouts, 5xx and 429 are retried with backoff (at most 3 attempts).
- 4xx, parse and robots errors are not retried.

*Acceptance criteria:*
- (a) For a fixture set of 10 feeds × 3 polls, `fetch_run` has exactly 30 rows.
- (b) A fixture returning 503 twice then 200 produces attempts 1–3 and a final `ok`.
- (c) A fixture returning 404 produces exactly 1 attempt.
- (d) A fixture returning malformed XML produces `error_class=parse` and 1 attempt.

**FR-04 · Feed health and incidents · MUST**

The system opens an incident when any of these happens:
- N consecutive failures (default 3);
- HTTP 200 with 0 entries while the 7-day median is > 0;
- no new item for more than k× the median inter-arrival time (default k = 6, minimum 6 h).

The incident closes on recovery. Opening and closing an incident raises a `feed_incident` alert. A notice to an outside
party (a wire agency) is only drafted, for approval.

*Acceptance criteria:*
- (a) Three failing polls open exactly one `failing` incident. One successful poll closes it.
- (b) A feed whose fixture switches to a valid empty RSS opens an `empty` incident on the first empty poll after the
  baseline.
- (c) The health page and `GET /api/v1/health/feeds` show the incident within one poll cycle.
- (d) A notice addressed to a non-allow-listed recipient lands in `outbox` with `status=awaiting_approval`. Nothing is
  sent.

### 5.2 Processing

**FR-05 · Normalisation · MUST**

Normalisation produces:
- the canonical URL (courlan, fragment stripped);
- NFC/NFKC text with HTML stripped;
- published time converted to UTC, with the raw string kept and the first-seen time recorded separately;
- the language, from feed metadata or script ratio;
- per-source boilerplate stripping;
- `content_sha256`.

Records that fail validation go to `quarantine` with a reason.

*Acceptance criteria:*
- (a) A fixture item with `pubDate` missing is stored with `published_utc=NULL`, `published_raw` empty and
  `first_seen_utc` set. It is not dropped.
- (b) A Hangul-majority title is labelled `ko`, a Han-only title `zh` and a Latin one `en` on the 30-item labelled fixture,
  with ≥ 29/30 correct.
- (c) A feed URL with `?at_medium=…` and `#frag` canonicalises to the bare article URL.
- (d) An item with an empty title is quarantined, with the reason recorded.

**FR-06 · Licence gate and DisplayPolicy · MUST**

- **Body fetch.** A body is fetched only when `storage ∈ {transient, full}`. A `transient` body is discarded after features
  are derived.
- **Single policy.** Every renderer (UI, API, MCP, digest, export) calls `DisplayPolicy`.
- **Recipients.** `redistribution` and `authorised_users` gate recipients.
- **Retention.** A nightly job purges data per `retention_days` and writes a purge receipt.

*Acceptance criteria:*
- (a) For a `storage=metadata` source, the fixture server sees no request to article pages, and `body_text` is NULL.
- (b) For `transient`, the body is requested once and `body_text` is NULL after processing.
- (c) For `display=headline`, the API, MCP, digest and HTML outputs contain no feed-summary text. This is checked by
  asserting the fixture summary string is absent from all four outputs.
- (d) A `redistribution=none` item placed in a digest to an external recipient renders as title + link only.
- (e) After a clock advance past `retention_days`, the body and AI outputs of that source are deleted, and an
  `audit_log` purge row lists the counts. Backup rotation never keeps a backup older than the shortest active
  `retention_days`, so the purge receipt also covers backups (known gap 4).
- (f) **AI fields obey `display` (V1-01).** `DisplayPolicy` governs `ai.*` fields as well as source fields. For an item
  whose source has `display < snippet`:
  - no `quote_original` and no translated verbatim quote is shown;
  - no source substring of 20 or more characters appears on any surface;
  - the Korean AI summary is shown only if `permitted_ops` contains `summarise` or `translate`. Otherwise only the Korean
    headline and the factual who/what/where/when and entity fields are shown.

  Whether a short-feed-summary rewrite counts as an "own-words summary" (DR-3) is OQ-12; this rule is the conservative
  default until OQ-12 is answered. Test: an AI stub returns a quote copied from the feed summary, and the API, MCP,
  digest and HTML outputs are asserted to contain no 20-character source substring.

**FR-07 · Exact dedup · MUST**

Exact duplicates are caught by source GUID or URI, by canonical URL, and by `content_sha256`.

*Acceptance criteria:*
- (a) The same URL seen in 2 feeds of one source creates 1 article and 2 `feed_entry` observations.
- (b) Re-running ingestion on the same fixture set creates 0 new articles (idempotent).
- (c) Two URLs with identical normalised content are linked as `same_item`.

**FR-08 · Near-duplicates, revisions and live items · MUST**

- MinHash-LSH (128 perms, char 4-grams). t ≥ 0.9 → `same_item`. t ≥ 0.5 → `syndicated` (cross-source) or `revision`
  (same source, within 48 h).
- `story_key` rules apply per source.
- Live items are excluded from near-dup linking.
- A NewsML-G2/AP-style higher version of the same `uri` becomes a new revision.
- A `pubstatus=canceled` item is marked `killed` and hidden from the queue.

*Acceptance criteria:*
- (a) On R6's labelled pairs (exported from private experiment data (not published) into a fixture), recall
  ≥ 0.95 for pairs with exact Jaccard ≥ 0.5.
- (b) A Yonhap "(종합)" fixture pair is linked as `revision` via `story_key`.
- (c) Two Guardian live-blog fixtures with shared boilerplate are not linked.
- (d) A wire fixture v2 of the same ItemID creates revision 2 of one article.
- (e) A kill fixture sets `status=killed`, and the item disappears from `GET /api/v1/events`.

**FR-09 · Source independence · MUST**

The independent-source count of an event = the number of distinct registrable domains (tldextract, offline suffix list)
whose items fall in distinct near-dup clusters.

*Acceptance criteria:*
- (a) On a fixture of 10 iHeart-style subdomain copies plus 2 other domains, the count is 3.
- (b) Two outlets carrying the same syndicated text count as 1.

**FR-10 · Event grouping · MUST**

- Incremental assignment over open events within a 48 h window.
- In O1: per-language TF-IDF (θ 0.2), plus gazetteer co-occurrence linking.
- In O3: embeddings (θs 0.55–0.6, θx 0.45).
- Editors can merge and split, recorded as `added_by=editor:<login>`.
- Every membership row records the algorithm id.

*Acceptance criteria:*
- (a) **O1** on R6's 240-item gold set (fixture copy): pair precision ≥ 0.80. Recall is reported, with no floor, because
  R6 measured 0.21.
- (b) [live or cached vectors] **O3** on the same set: pair F1 ≥ 0.70 and B³ F1 ≥ 0.85. R6 measured 0.776 and 0.901,
  tuned on the same set, so the floors sit below those.
- (c) Merge then split restores the original memberships. Both actions are audited.
- (d) An item whose source has `external_ai_allowed=false` and no customer endpoint is never sent to the embedding
  provider, whatever the mode. The AI stub's call log shows 0 calls for it.

### 5.3 AI (optional; O2/O3)

**FR-11 · Triage band · MUST (when enabled)**

- The rules band is computed first. Then the Haiku triage band is computed, on title + lead.
- Final band = max(rule band, LLM band), with the LLM capped at `report`.
- `flash` comes only from rules.

*Acceptance criteria:*
- (a) An AI stub returning `flash` cannot make an item `flash` when no rule fires.
- (b) With `ai.capabilities.triage=false`, 0 triage calls are made and bands equal the rule bands.
- (c) The triage output is stored in `ai_interpretation` with model, prompt version and cost.

**FR-12 · Enrichment · MUST (when enabled)**

One tool-less, schema-constrained call per item at band ≥ `review`, where the item is allowed. It returns:
- a Korean headline and 3-sentence summary;
- key quotes translated, with the originals kept;
- who/what/where/when;
- entities with `name_original` and `name_ko`;
- claims with `attributed_to`;
- `injection_suspected`.

*Acceptance criteria:*
- (a) [live] On a 20-item fixture (EN/ZH/KO), 100% of outputs are schema-valid after at most one retry. Every
  `name_original` appears verbatim in the input in ≥ 95% of entities. Every number in the summary appears in the source.
  This is checked automatically.
- (b) The request payload contains only the fields allowed by `storage` and `ai_processing`. For `unknown`, that means
  title + feed summary. Checked from the logged `fields_sent`.
- (c) Re-enriching an unchanged item makes 0 provider calls (cache hit).

**FR-13 · Validation and review queue · MUST (when enabled)**

There are three validation layers: API schema, Pydantic, and semantic checks (Hangul ratio ≥ 0.5 for Korean fields,
entity grounding, numbers preserved). An item that fails gets one retry, then goes to the review queue. A failure is never
retried in bulk.

*Acceptance criteria:*
- (a) An AI stub returning an English "Korean summary" fails the Hangul check, retries once, and lands in UI-9 with
  `validation_status=review`.
- (b) A batch of 50 deterministic failures produces exactly 100 calls, not more.

**FR-14 · Injection handling · MUST (pre-filter in every mode; model flag when AI is enabled)**

- Detection: an EN/KO/ZH regex pre-filter, which **runs in every mode including O1** (FR-21(c) depends on it), OR-ed
  with the model flag when AI is on.
- A flagged item has its LLM band discarded and is set to `review` with a ⚠ tag.
- It is never auto-alerted or auto-placed in a digest.

*Acceptance criteria:*
- (a) Each of R7's attack fixtures ([`experiments/ai-processing/prompts/attacks.json`](../experiments/ai-processing/prompts/attacks.json), A1–A3) yields
  `injection_suspected=1` or `regex_prefilter_hit=1`, band `review`, and no alert.
- (b) The 44 clean hardened fixtures yield ≤ 2 regex false positives.

**FR-15 · AI routing, degradation, cost cap · MUST**

**Routing per item:**
- If `ai_processing=no`, or the op is not in `permitted_ops`, or the capability is off → O1 path.
- If `external_ai_allowed=false` → customer-hosted endpoint only. If none exists → O1 path, with
  `enrichment_status=not_allowed`.

**Spend and outages:**
- There is a daily USD cap (default 5). When it is hit, the system degrades to O1 until midnight KST.
- On a provider outage, items stay `pending`, and a worker drains them on recovery with backoff.

*Acceptance criteria:*
- (a) With no API key configured, the full O1 acceptance suite (§5.7) passes, and the UI header shows "AI: 꺼짐".
- (b) With an AI stub raising 503 for 10 minutes, collection, dedup, search and alerts continue (items keep appearing in
  the queue). After recovery all `pending` items reach `done` or `review`.
- (c) With the cap set to $0.01 and the stub reporting $0.004 per call, the 4th call is not made and `spend_day.capped=1`.
- (d) A `mock_wire_gated` item produces 0 calls to any hosted provider.

### 5.4 Profiles and ranking

**FR-16 · Monitoring profiles without code · MUST**

Profiles (INTERFACE_SPEC §7) define:
- topics with KO/EN/ZH keywords;
- entities (gazetteer ids);
- countries, languages and exclusions;
- source weights and mutes;
- ordered priority rules;
- thresholds;
- alert channels and recipients;
- digest schedules.

They are edited as a form or YAML, validated on save, versioned, and exportable.

*Acceptance criteria:*
- (a) Adding a keyword in the UI changes the ranking of a matching fixture item on the next evaluation, with no restart and
  no code change.
- (b) A profile with an unknown source id or entity id is rejected with a message.
- (c) A rule that sets `flash` from an AI field is rejected.
- (d) `config export` then `import` into an empty instance reproduces identical profile YAML (byte-equal after
  normalisation).
- (e) The "last 24 h preview" counts match a direct rule re-run over the same stored items.

**FR-17 · Rule-based relevance with explanation · MUST**

The score is a weighted sum of:
- watch-term and entity hits;
- country match;
- source weight;
- independent-source count;
- urgency (wire);
- recency;
- event size;
- spike flag (rolling z ≥ 2.5 over 7 buckets, minimum count 5).

Weights come from config. Every banded item shows which rules fired and which terms matched.

*Acceptance criteria:*
- (a) On a 30-item hand-labelled fixture with expected bands from a fixed profile, the band is exactly as expected for
  ≥ 28/30.
- (b) Every item at band ≥ `review` has a non-empty `rule_hit` explanation.
- (c) A synthetic hourly series with one 3× peak flags the peak bucket and no other.

### 5.5 Delivery surfaces

**FR-18 · Editorial queue and verdicts · MUST**

The queue (UI-1) lists events by band, then independent sources, then recency. It filters by band, language, source,
profile and time. Verdicts are `report_to_desk`, `verify`, `ignore` and `archived`, each with a note, stored in
`editorial_assessment` apart from AI output. The queue is keyboard operable.

*Acceptance criteria:*
- (a) After ingesting the fixture set, the queue renders in < 1 s (p95 over 20 loads) with 500 events.
- (b) A verdict writes one assessment row, with editor and time, and leaves AI rows unchanged.
- (c) A verdict is reachable with keyboard only (j/k/r/v/x).
- (d) In O1, every row shows the original headline and a band. No row is blank.

**FR-19 · Event and item detail with provenance · MUST**

Event detail shows members in time order, the independent-source count, and the near-dup and revision relations. Every
item shows source, link, publisher time and first-seen time, display level, and AI fields labelled with model and
prompt version.

*Acceptance criteria:*
- (a) Every item rendered on the event page has a source name and either a working link or "원문 보기" for `display=full`.
- (b) AI text is wrapped in an element carrying the "AI 생성" label in 100% of renders, checked by an HTML assertion.

**FR-20 · Search · MUST**

- BM25 over the bigram FTS5 index.
- Filters: language, source, time, band and event.
- Alias expansion from the gazetteer, shown on screen.
- Optional LLM query rewrite (O2).
- A banner shows failing feeds within the filter.

*Acceptance criteria:*
- (a) R6's 10 known-answer queries per language (KO, ZH) reach recall 1.00 on the fixture corpus, including the
  2-character queries 북한, 미국, 中国, 美国.
- (b) The 3 nonsense queries per language return 0.
- (c) Searching "Kim Yo Jong" returns the KO and ZH fixture items for 김여정/金與正 via the gazetteer, in O1.
- (d) p95 latency < 300 ms on 100,000 synthetic rows.

**FR-21 · Alerts · MUST**

Flash and spike alerts are raised per profile rule and de-duplicated per event (one alert per event per 6 h, unless the
band rises). They go in-app (badge, and a browser notification while open) and by email.
- Sending is automatic only to allow-listed internal recipients, and only for unflagged items.
- Everything else waits in the outbox for one-click approval.

*Acceptance criteria:*
- (a) A wire fixture with `URGENCY: 1` matching the profile produces exactly one flash alert, and one email to the test
  SMTP sink, within 60 s of the file appearing in the inbox.
- (b) A second member of the same event produces no second email.
- (c) An injection-flagged item produces no email.
- (d) A recipient outside the allow-list produces `awaiting_approval` and nothing is sent.

**FR-22 · Digests and shift handoff · MUST**

Each profile has scheduled editions (morning, evening, handoff) and ad hoc editions.
- **Selection** is by rules.
- **Draft:** Sonnet with cited article ids (O2), or a template (O1).
- **Citation check:** every bullet must cite at least one article, and every cited id must belong to the selected set.
- **Review:** a person reviews and edits, then approves.
- **Send:** email.
- **Record:** a delivery log of sent and failed messages per recipient.

*Acceptance criteria:*
- (a) At the scheduled time (simulated clock), a draft exists, with `status=in_review`, and is not sent.
- (b) An AI stub draft that cites an id outside the selection fails the citation check and cannot be approved.
- (c) Approving sends to the SMTP sink and writes one `delivery_log` row per recipient. A recipient the sink rejects shows
  `failed`.
- (d) In O1, a template digest with titles, links and source counts is produced for the same window.
- (e) **Per-item licence gate on AI drafts (V1-02).** The draft prompt is built item by item through `LicenceGate`. An item
  whose source forbids the op, or has `external_ai_allowed=false` with no customer-hosted endpoint, enters as
  `[id, headline withheld]` or appears only as a template line. Test (AI stub): a digest containing a `mock_wire_gated`
  item sends 0 bytes of its text to the hosted provider. The same rule applies to MCP `get_briefing` when the briefing
  is AI-drafted.

**FR-23 · Read-only JSON API · MUST**

The endpoints are those in deliverable 11 §6. Authentication is a bearer token (stored hashed, scope `news.read`). All
text passes through `DisplayPolicy`. AI fields are nested under `ai` with `generated_by_ai: true`.

*Acceptance criteria:*
- (a) No token returns 401. A revoked token returns 401.
- (b) The responses for a `display=headline` item contain no summary text, as in FR-06(c).
- (c) Every list endpoint caps `limit` at 50.

**FR-24 · Read-only MCP server (stdio) · SHOULD**

The tools are `search_articles`, `get_article`, `get_event`, `list_events`, `list_alerts`, `get_briefing`,
`get_feed_status` and `list_sources`.
- Source text sits under `untrusted_source_text`, with `content_trust`.
- There are no write, SQL or URL-fetch tools.
- **Items with `external_ai_allowed=false` return only metadata and headline**, because the MCP client is usually a hosted
  model.

*Acceptance criteria:*
- (a) The MCP tool list contains exactly the 8 read tools.
- (b) `get_article` on a `mock_wire_gated` item returns no body text.
- (c) `get_article` on a public item puts its text under `untrusted_source_text`.
- (d) The server opens the DB read-only. An attempted write raises an error.

**FR-25 · AI labelling and safe rendering · MUST**

- All generated output carries `generated_by_ai`, a model and a prompt version, and shows "AI 생성" in the UI, digest,
  API and MCP (DR-8).
- Model output is rendered as plain text, with links stripped.

*Acceptance criteria:*
- (a) An AI stub output containing `<img src=…>`, a markdown link and `http://exfil.example` renders as inert text, with
  no `<a>`, `<img>` or URL in model fields.
- (b) Every digest generated by AI carries the label in the subject line or the first line.

**FR-26 · Audit log, takedown and purge · MUST**

The audit log records:
- fetches, with the licence flags;
- AI calls, with the fields sent, provider and region;
- verdicts, profile changes, sends, exports, purges, takedowns, and MCP/API calls.

Takedown disables a source and purges its stored content on command.

*Acceptance criteria:*
- (a) Each listed action type produces one `audit_log` row in an end-to-end run.
- (b) `newsmon source takedown <key> --purge` leaves 0 article rows for that source, and writes a receipt with the counts.
- (c) No `audit_log` row contains a secret. A grep for configured key values finds 0 matches.

### 5.6 Source connectors (supplement 02; ADR-010)

**FR-27 · Generic connector contract · MUST**

All inputs pass through `Connector.poll/parse/health`, producing a `NormalisedItem` in ninjs-style fields with provenance
(`raw_ref`, `raw_sha256`, `parser`, `received_utc`, `synthetic`, `licence_snapshot`). Downstream code never branches on
connector kind.

*Acceptance criteria:*
- (a) The same story, delivered once as RSS and once as a plain-text wire file, produces two `NormalisedItem`s with
  identical field sets, linked by dedup.
- (b) Every article row has a non-null `licence_snapshot` and `raw_sha256`.
- (c) A connector whose remote fails returns `status=error:<class>` and raises no exception, checked by a fault-injection
  test.
- (d) **`synthetic` is provenance only (V1-04).** It never alters a `LicenceGate` or `DisplayPolicy` decision. With the
  same flags, `synthetic=true` and `synthetic=false` give the same route and the same rendering. This overrides the
  wording of DR-17 in deliverable 08, which said that synthetic data bypasses licence logic.

**FR-28 · Watched inbox directory · MUST**

The watcher is read-only and confined to its root (symlink escape refused). It scans every 10 s by default (configurable;
V1-06, so that the 60 s alert criterion of FR-21(a) holds). It ingests a file only after the file's size and mtime have
been stable across two scans. It keeps a ledger keyed by path, size, mtime and sha256. It parses AP-style
`ItemID--Version--ContentID` names. It tolerates files disappearing. It never modifies or deletes customer files.

*Acceptance criteria:*
- (a) Copying the fixture inbox (≥ 18 files) into the watched directory ingests every valid file within 2 scan intervals.
- (b) Re-scanning ingests nothing new.
- (c) A file still being written (its size changes between scans) is not ingested until stable.
- (d) The symlink to a file outside the root is refused, with `error_class=io`.
- (e) After the run, the directory's file list and hashes are unchanged.
- (f) Deleting a file after ingest leaves the item intact and marks the ledger `gone`.

**FR-29 · Wire-format parsers and fixtures · MUST**

There are parsers for NewsML-G2 (XML, safe parsing), NITF, ninjs JSON, and the project's plain-text wire format, with
detection by content. Media files become `media_asset` references only.

*Acceptance criteria:*
- (a) Every fixture item maps headline, `versioncreated`, language, urgency, body and `pubstatus` to the expected values in
  a golden JSON file. Field-level equality.
- (b) The NITF shotlist becomes an association on the video item.
- (c) Each malformed fixture is quarantined with a reason.
- (d) An XML fixture containing an external-entity declaration is refused, and no outbound request or file read occurs.
- (e) A video fixture creates one `media_asset` row with sha256 and size, and no copy of the media file exists under the
  data directory.

**FR-30 · Customer-entered licence terms with attestation · MUST**

The onboarding form (UI-8) records the customer's contract terms as flags, using the DR-30 checklist and the DR-17 fields
(`licence_holder`, `agreement_ref`, `valid_until`, `attested_by`, `attested_on`, `retention_days`, `display`,
`permitted_ops`, `external_ai_allowed`, `third_party_processors_allowed`, `redistribution`, `authorised_users`).

- A `licence_owner=tenant` source cannot be activated until it is attested and `retention_days` is set.
- Ingestion stops after `valid_until`.
- The defaults for an unconfigured source are a safety choice, not a claim about any contract.

*Acceptance criteria:*
- (a) Activating a tenant source without attestation fails, both via the DB CHECK and in the UI.
- (b) After `valid_until` (simulated clock), the next poll is skipped, with an audit row.
- (c) Changing `external_ai_allowed` from false to true on `mock_wire_demo` makes the next item eligible for enrichment.
  The change is audited.
- (d) `third_party_processors_allowed=false` on any active tenant source makes `newsmon doctor` report "deployment must be
  customer-hosted" when `settings.deployment_model ≠ CH`.

**FR-31 · Video-ready item schema · MUST**

Items carry the ninjs fields `type`, `slugline`, `located`, `urgency`, `usageterms`, `restrictions`, `renditions` and
`associations`. An unknown `restrictions` value is treated as restricted, which means display is capped at `headline`.

*Acceptance criteria:*
- (a) The ninjs video fixture round-trips through `GET /api/v1/articles/{uid}` with its renditions intact.
- (b) A fixture with an unrecognised restriction string renders headline-only.

### 5.7 O1 mode acceptance (no AI provider configured)

These run with `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` unset and `ai.capabilities` all false. They are acceptance
criteria in their own right.

| ID | Criterion |
|---|---|
| **AC-O1-01** | The end-to-end run on the fixture set completes. Collection → dedup → grouping → rules → queue → alert → digest all run, with 0 outbound connections to any AI host (checked against a network deny-list in the test) |
| **AC-O1-02** | FR-01…FR-10, FR-16…FR-23 and FR-25…FR-31 acceptance criteria pass, excluding those marked [live] |
| **AC-O1-03** | Every queue row shows an original headline, source, time and a band. The header says "AI: 꺼짐". Items carry no "AI 처리 대기" (that tag means AI is configured but pending) |
| **AC-O1-04** | A flash wire fixture produces an alert within 60 s. The template digest is produced, approved and sent to the SMTP sink |
| **AC-O1-05** | Event grouping precision ≥ 0.80 on R6's gold set (FR-10(a)). The measured recall is printed in the test report, not hidden |
| **AC-O1-06** | Search "Kim Yo Jong" finds KO and ZH gazetteer matches (FR-20(c)). A query for a non-gazetteer English phrase does **not** find Korean coverage. That is recorded as a known O1 limit, expected by the test |

## 6. Supported sources (initial seed; ADR-002)

The flags below are the values written into `config/sources.yaml`. IDs are `source_id`s in
[`sources-and-licensing/source-registry.csv`](../sources-and-licensing/source-registry.csv). "Context" says where a source runs: `P` = private only, `P,I` = both. Public
sources are polled every 600 s by default (GDELT every 900 s).

| source_id | Lang | Storage | Display | AI processing | External AI | Context | Basis (registry `commercial_use`, deliverable 04/08) |
|---|---|---|---|---|---|---|---|
| sec_edgar_atom_8k (inactive by default) | en | full | full | yes | true | P,I | SEC reuse free (VERIFIED in deliverable 04) |
| sec_pressreleases | en | full | full | yes | true | P,I | same |
| fedreg_api | en | full | full | yes | true | P,I | US federal text, public domain under 17 U.S.C. §105 (INFERRED, `08_LEGAL…` §5). Registry `commercial_use` UNVERIFIED |
| un_press | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| gdelt_lastupdate | en | metadata | headline | unknown | true | P,I | GDELT open licence, citation required (VERIFIED, F-L-05) |
| guardian_world | en | metadata | headline | unknown | true | P | personal, non-commercial |
| bbc_world | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| aljazeera_all | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| dw_en_all | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| france24_en | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| cna_sg_all | en | metadata | headline | unknown | true | P | personal, non-commercial |
| npr_news | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| scmp_world | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| yna_news, yna_intl, yna_nk | ko | metadata | headline | unknown | **false** | P | non-commercial; written licence needed for commercial use. Footer AI wording suggests an AI restriction, so the flag is false per 08 §13.4 (V1-03), and these rows run in O1. A tenant's 연합뉴스 contract is configured as a separate tenant source |
| khan_total | ko | metadata | headline | unknown | true | P | permission needed for commercial use |
| donga_intl | ko | metadata | headline | unknown | true | P,I | terms UNVERIFIED; no GUID, so dedup is on link |
| hankyung_intl | ko | metadata | headline | unknown | true | P,I | terms UNVERIFIED; title + link only |
| rfi_zh, voa_zh, bbc_zh_simp, dw_zh_all | zh | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| cna_tw_intl, cna_tw_mainland | zh | metadata | headline | unknown | true | P | non-commercial; ignores conditional GET |
| scmp_china, cgtn_china | en | metadata | headline | unknown | true | P,I | terms UNVERIFIED |
| **mock_wire_gated** (directory) | en/ko | full | full (internal users) | yes, `permitted_ops=[]` | **false** | P,I | synthetic; attested with the most restrictive flags; `retention_days=7` |
| **mock_wire_demo** (directory) | en/ko | full | full (internal users) | yes, all ops | true | P,I | synthetic; attested example flags |

**How the seed behaves:**
- In `internal` context, 8 of the 27 public rows are inactive (the `P` rows).
- In `private` context, all 27 public rows plus the 2 mock rows run.
- A customer's real AP, Reuters or 연합뉴스 source is added at onboarding with that customer's own terms (FR-30).

## 7. User workflows

| ID | Workflow | Steps |
|---|---|---|
| WF-1 | Shift monitoring | Open the queue (profile 외신데스크) → scan FLASH/REPORT rows → open an event → [보고] with a note (this is the "PC등록") or [확인]/[무시] → the next shift sees the verdicts |
| WF-2 | Flash notice | A rule fires (a wire urgency-1 item or a multi-source watch entity) → in-app badge and email to desk@ → the monitor opens the event → registers it |
| WF-3 | Reporter request | Search (KO/EN/ZH) → item detail → copy the provenance (source, link, time) and the AI summary (labelled) |
| WF-4 | Handoff / morning briefing | At the scheduled time a draft is created (AI or template) → the editor edits, reorders and removes items → approves → email is sent → the delivery log is checked |
| WF-5 | Feed incident | An incident opens → the health page shows it → an internal alert goes out → the outside notice is drafted for approval → the incident auto-closes on recovery |
| WF-6 | Profile change | Edit the profile (form or YAML) → preview "last 24 h" → save (versioned) → takes effect next cycle |
| WF-7 | Onboard a licensed source | Admin adds a directory source → completes the DR-30 checklist with the contract's terms → attests → activates → watches the first ingest in the health page |
| WF-8 | AI outage | The provider fails → the header shows "AI: 중단" → work continues in O1 → the backlog drains on recovery |

## 8. Data model

The data model is deliverable 11 §5 (SQLite DDL), built on R6's model. Principles:
- Source text, AI interpretation and editorial judgement live in separate tables.
- Observations are immutable and revisions are versioned.
- Natural keys make ingestion idempotent.
- Timestamps are stored in UTC.
- `workspace_id` appears on every owned table.
- Licence flags are snapshotted on every article.

## 9. Interface requirements

| ID | Requirement | Spec |
|---|---|---|
| IR-01 | The UI surfaces UI-1…UI-9 exist and are in Korean, with KST display | INTERFACE_SPEC §1–§8 |
| IR-02 | The JSON API endpoints follow the stated shape | deliverable 11 §6 |
| IR-03 | The MCP tools follow [`technology/mcp-tool-design.md`](../technology/mcp-tool-design.md) §3 v1, with the FR-24 gating | — |
| IR-04 | Email has plain-text and HTML parts, the subject prefixes `[newsmon][FLASH]` / `[newsmon][조간]`, and AI is labelled | — |
| IR-05 | Configuration files follow the layout in deliverable 11 §9, with `ai.capabilities` in `settings.yaml` | — |
| IR-06 | The CLI provides `init`, `serve`, `migrate`, `backup`, `restore`, `export`, `import`, `config export/import`, `source takedown`, `doctor` and `sbom` | — |

## 10. Non-functional requirements

| ID | Requirement | Acceptance criterion |
|---|---|---|
| NFR-01 Latency | New item visible in the queue quickly | Public feed: ≤ poll interval + 120 s at p95. Inbox file: ≤ 60 s at p95 (O1). Enrichment adds ≤ 60 s at p95 [live] |
| NFR-02 Throughput | Handles MVP daily volume | A replay of 5,000 fixture items (AI stub) is fully processed in ≤ 30 min on the dev machine |
| NFR-03 Politeness | No over-fetching | Minimum poll interval 300 s per feed; ≤ 1 concurrent request per host (FR-02(e)); a descriptive UA on 100% of requests |
| NFR-04 Restart recovery | A crash loses nothing | Killing the process during ingest, then restarting, gives `PRAGMA integrity_check = ok`, 0 duplicate articles, and resumed polling and inbox scanning |
| NFR-05 Idempotency | Re-running produces nothing new | Running the pipeline twice on the same inputs gives identical row counts in all content tables |
| NFR-06 SSRF / fetch safety | No requests to internal addresses | FR-02(d); a response size cap of 10 MB and a 30 s timeout are enforced (test with an oversize fixture) |
| NFR-07 Secrets | Keys never leak | No secret in logs, DB, API or MCP output (a grep test over all outputs of the e2e run) |
| NFR-08 Untrusted content | Untrusted text cannot steer actions | No `tools` parameter in any content-processing request (asserted in the provider adapter test); FR-25 rendering |
| NFR-09 AI spend | Spend is capped | Daily cap enforced (FR-15(c)); an alarm at 2× expected spend |
| NFR-10 Search regression | Known searches keep working | FR-20(a)(b) run in CI |
| NFR-11 Dedup regression | Known duplicates stay linked | FR-08(a) runs in CI |
| NFR-12 Observability | Health is visible | `/healthz` and `/metrics` expose: fetch success rate (24 h), open incidents, enrichment backlog, items per hour, alerts, AI spend against the cap, DB size; each value is checked against the fixture-run truth |
| NFR-13 Logging | Logs are machine-readable | JSON lines; one record per fetch run, AI call, alert, send and error, each with a correlation id |
| NFR-14 Locale | Korean UI, correct time zones | Korean UI strings; KST display, UTC storage (a DST-free check of stored vs displayed time) |
| NFR-15 Privacy (DR-9) | Personal data handling is controlled | `fields_sent` is logged per AI call; there are no person-profile pages; the AI provider and region come from config; an entity-masking switch exists for AI inputs, and with it on, PERSON entities from the gazetteer are replaced before the call (checked in the stub log) |
| NFR-16 Reproducibility | Every derived result can be traced | Every derived row records the algorithm, model or prompt version; re-running the clustering with the same algo id on the same input yields the same memberships |
| NFR-17 Platform | Runs on plain machines | Runs on Windows 11 and Linux with Python ≥ 3.12, without Docker and without any local model |
| NFR-18 Dependency hygiene | Dependencies are pinned and clean | A lock file; `pip-audit` reports no known high or critical vulnerability at release |
| NFR-19 No training | No model is trained | No code path calls a training or fine-tuning API (static check of the provider adapter); `training` is fixed to `no` |

## 11. Deployment flexibility constraints (ADR-009)

These are the DECIDE-NOW items, stated as NFRs.

| ID | Constraint | Acceptance criterion |
|---|---|---|
| NFR-20 | 12-factor config and state | The app boots against fixtures with `NEWSMON_CONFIG_DIR`, `NEWSMON_DATA_DIR` and the DB path supplied only by environment variables, and writes nothing outside the data dir (a file-system diff before and after). A Dockerfile is provided as an artefact, **untested (no Docker on this machine)** |
| NFR-21 | Ports and adapters | An import-lint test: modules under `domain/` and `pipeline/` import none of `sqlite3`, `httpx`, `anthropic`, `smtplib` |
| NFR-22 | Repository layer and portable DDL | All SQL lives under `repo/`; a grep test finds no SQL strings elsewhere; the DDL uses only the portable types listed in ADR-004 |
| NFR-23 | Tenant seam | Every owned table has `workspace_id NOT NULL` (schema introspection test); every repository query includes it (a query-log test over the e2e run) |
| NFR-24 | Per-instance isolation; isolated collection | Two instances with different data dirs on one host share no file, cache or DB (the e2e test runs both and diffs the open file handles and paths) |
| NFR-25 | Auth seam | The `AuthProvider` interface has `local` and `static_users` implementations; roles are enforced (a viewer cannot post a verdict: 403); tokens are stored only as hashes |
| NFR-26 | Configuration portability | `config export` → `import` into a clean instance reproduces sources, profiles, rules, schedules and recipients (row and byte equality), with secrets excluded |
| NFR-27 | Credential seam | All secrets are read via `SecretStore`; a grep test finds no `os.environ` reads of secrets elsewhere; each credential carries an `owner` tag |
| NFR-28 | Install and migrate | A fresh `uv venv` + install + `newsmon init` + `newsmon serve` works on Windows and Linux; `migrate` takes an automatic pre-migration backup (the file exists and passes `integrity_check`) |
| NFR-29 | Backup, restore, export, deletion | `backup` → delete DB → `restore` gives identical row counts. A full `export` → `import` round-trip gives identical row counts. Export omits bodies whose flags forbid export (assert absent). `delete-all --confirm` leaves 0 content rows and writes a report |
| NFR-30 | Usage recording | Every AI call stores tokens and `cost_usd`; every fetch run stores bytes; `/metrics` sums match the table sums |
| NFR-31 | OSS licence posture | CI generates an SBOM and `THIRD_PARTY_NOTICES`; a licence check fails the build on AGPL, SSPL, GPL or Sustainable Use licences in the core dependency set |

**Explicit deferrals (ADR-009 DEFER, with their triggers):**

| Deferred item | Trigger |
|---|---|
| PostgreSQL adapter | R6 migration trigger or SaaS |
| Multi-tenant enforcement | SaaS |
| SSO | Customer IdP requirement |
| Encrypted vault | MP/SaaS |
| Shared public collection | SaaS with more than about 10 tenants |
| Licence keys and entitlements | First paid CH distribution |
| Auto-update channel | More than a handful of CH installs |
| Billing-grade metering | SaaS or usage pricing |
| Tested container images | A customer requires containers |

## 12. Deployment requirements

| ID | Requirement |
|---|---|
| DEP-01 | Local install on Windows 11 with Python 3.12+ in a `uv` venv on a short path (MAX_PATH issue). `newsmon serve` binds 127.0.0.1, `auth=local` |
| DEP-02 | Small Linux VPS (1–2 vCPU, 2 GB RAM): a systemd service, a reverse proxy with TLS (product choice open), `auth=static_users`, the data dir on a persistent disk, daily backup copied off-host |
| DEP-03 | Customer-hosted pilot: the same artefact, installed in the customer's network; the watched inbox mounted read-only from the customer's Media Agent output directory |
| DEP-04 | Secrets only in `.env` or the environment, never in config files or the DB |
| DEP-05 | Before any real licensed source is enabled, the FR-30 attestation is complete. Under MP, the customer's contract must permit third-party processors (`08_LEGAL…` §13.1) |

## 13. AI-off degradation behaviour

O1 is the specified behaviour when no provider is configured, when the provider is unavailable, when the daily cap is
reached, or when the item's flags forbid AI (FR-15, §2, §5.7).

**What the user sees:**
- **Header:** "AI: 꺼짐" when AI is not configured, "AI: 중단" when it is configured but failing or capped.
- **Items waiting for enrichment** (configured but pending): tagged "AI 처리 대기".
- **Items whose flags forbid AI:** tagged "AI 미적용 (라이선스)".

**What keeps running:** collection, dedup, grouping, rules, search, queue, alerts, feed health and template digests. Each
runs with its O1 quality (§2), which is lower on cross-lingual linking and gives no Korean summaries.

## 14. Open questions

| ID | Question | Owner | What it changes |
|---|---|---|---|
| OQ-1 | **For each pilot customer: what does its AP, Reuters or 연합뉴스 contract allow** (service providers, storage days, AI inference by hosted or customer-hosted models, recipients)? The contracts are not public. APA's published terms are only an example | Customer + counsel | That customer's flag values and deployment model (CH vs MP). No code change |
| OQ-2 | Terms of the 12 publishers whose RSS terms were not read (`04_INFORMATION…` F-D-02) | R5 round 2 | `allowed_contexts` and `display` per source |
| OQ-3 | Is internal organisational use within the "personal / non-commercial" wording of the Yonhap, Kyunghyang, Guardian and CNA feeds? | Korean counsel | Seed `allowed_contexts` |
| OQ-4 | Does `kiwipiepy` fit the no-local-inference policy? | User | Optional ranking improvement only |
| OQ-5 | The PIPA §28-8 route for sending names in news text to a US-hosted LLM | Counsel | Default AI routing for KR customers; entity masking; customer-hosted endpoint |
| OQ-6 | BYOK under OpenAI §3.3(g), and Anthropic's position, in writing | Vendors | Whether BYOK is offered |
| OQ-7 | A desk-labelled gold set for relevance, clustering and summary acceptability | S2 / round 2 | Thresholds, the LLM band weight, Haiku vs Sonnet routing |
| OQ-8 | The State Department briefing archive (R-23): state.gov returned 403 | R5 round 2 | Whether R-23 can be served from an authorised source |
| OQ-9 | Build-time checks not done in phase 1: FTS5 `contentless_delete`, the MCP SDK version, defusedxml, tldextract offline mode, FastAPI/htmx in practice | First backlog tasks | Minor implementation choices |
| OQ-10 | Which ingest tool, NRCS and MAM each Korean channel runs, and who operates Media Agent (`02_COMMERCIAL…` §8.3) | Round-2 interview | Pilot connector priorities |
| OQ-11 | The Arirang APTN contract record (₩888,030,000) was not located by R2 (six searches) | R2 round 2 | Market evidence for Model B buyers only |
| OQ-12 | Does a Korean AI rewrite of a 1–2 sentence feed summary from a `display=headline` source count as an "own-words summary" (DR-3), or as a translation (08 §6 row a5, conditional)? | User + Korean counsel | Whether FR-06(f) can show Korean summaries for public headline-only sources without `permitted_ops ∋ summarise` |
