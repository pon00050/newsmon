# ADR-002 · MVP source set (D2): keyless public feeds and official APIs, with registry licence flags that drive behaviour

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: Built; public feeds are not sent to AI unless an operator changes a source's flags (decision log P-013).
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Informs:** deliverable 12 §6 (supported sources), FR-01, FR-06, ADR-009.

## Context

- Technically, publisher RSS works in EN/KO/ZH: 36 of 36 probed feeds returned 200, median 0.06 s (TESTED,
  private experiment data (not published); [`sources-and-licensing/information-source-and-api-registry.md`](../../sources-and-licensing/information-source-and-api-registry.md) F-D-01).
- Legally, most working KO/ZH (and some EN) feeds say "personal, non-commercial" (DOCUMENTED, F-D-02;
  private experiment data (not published)).
- R9 gives a licence-free floor (headline + link + source + own-words summary), source tiers and DR-1…DR-15
  ([`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §5, §6, §8).
- AP and Reuters are not collectable without the customer's contract (F-D-03; [`business/commercial-product-landscape.md`](../../business/commercial-product-landscape.md) F-B-01).
- GDELT KO/ZH is unestablished (empty results, 429s; F-D-05).
- YouTube channel RSS: R8 fetched one feed (TESTED, 15 entries, [`experiments/multimedia/results.md`](../../experiments/multimedia/results.md) §6), but youtube.com
  robots.txt contains `Disallow: /feeds/videos.xml` for `*` (VERIFIED, F-D-04), and the YouTube API policies forbid storing
  audiovisual content and require refreshing stored API data within 30 days (VERIFIED, `08_LEGAL…` F-L-05).

## Options considered

1. **Clean core only** (government/open-licence sources: SEC, Federal Register, GDELT, UN press). Legally safest; useless
   for a desk that watches foreign news.
2. **Clean core + public publisher feeds at the licence-free floor, gated by per-source flags and by the deployment's use
   context.** Matches R5's recommended set and R9's DR-1/DR-3/DR-4.
3. **Option 2 plus generated feeds and page change detection** (RSSHub, changedetection.io) for KBS, YTN, Xinhua etc. Adds
   services; inherits each site's terms; not needed for the MVP's languages ([`sources-and-licensing/acquisition-methods.md`](../../sources-and-licensing/acquisition-methods.md) §4).
4. **Licensed wires** (AP Media API, Reuters Connect). Impossible to build or test here (non-goal).

## Decision

**Option 2.** The source registry is data (YAML seed → `source` table) and carries R9's DR-1 flags. Behaviour follows the
flags, never source-specific code:

| Flag (DR-1) | Values | Behaviour it drives |
|---|---|---|
| `storage` | none / metadata / transient / full | `metadata` = title, URL, GUID, timestamps, the feed-supplied summary, hashes and MinHash kept; no body fetch. `transient` = body fetched, features/summary derived, body discarded (DR-4). `full` = body retained |
| `display` | none / headline / snippet / full | `headline` = title + link + source + time (+ AI own-words summary, labelled). `snippet` adds the feed summary. `full` only for public-domain/official or tenant-licensed items (DR-3) |
| `ai_processing` | yes / no / unknown | `yes` = the LLM may read every stored field. `unknown` = the LLM may read only what `storage` keeps (title + feed summary), never a fetched body. `no` = no LLM or embedding call; TF-IDF clustering fallback for that item |
| `external_ai_allowed` | true / false (S1 addition for supplement 02) | `false` = the item may be sent only to a customer-hosted AI endpoint; if none is configured, the item gets no LLM or embedding call (rules + TF-IDF path). Default `true` for public feeds at the floor (only title + feed summary leave the system), **`false` for an unconfigured `licence_owner=tenant` source** until the customer enters its contract terms (ADR-010) |
| `licence_owner` | provider / tenant / public-domain / unknown | `tenant` unlocks the source in `internal` context (BYOL, DR-15) |
| `allowed_contexts` | `private`, `internal` (S1 addition) | A source whose terms say "personal / non-commercial" runs only when `deployment.use_context=private`, unless `licence_owner=tenant` |
| `retention_days`, `redistribution`, `training` (default no), `attribution_text`, `tos_url`, `tos_checked_on`, `robots_ok`, `access_method` | as DR-1 | retention purge job; export filter; attribution on every display (DR-12) |

Default for any unknown value: `storage=metadata`, `display=headline`, `ai_processing=unknown`, `training=no` (DR-1).

**Customer-licensed sources (Model B, supplement 02)** enter through the connectors of ADR-010: a watched inbox directory
for AP Media Agent output and equivalent vendor ingest, plus customer-credentialed wire API connectors (designed, deferred).
**Their licence behaviour is configured by the customer**, from that customer's own contract. At onboarding the customer
enters the contract's terms as flags and attests to them (DR-17, DR-30; ADR-010 §4). An unconfigured tenant source stays
disabled. Its safe defaults are `external_ai_allowed=false`, `redistribution=none` and no AI ops. Those defaults are a
safety choice, not a claim about what any wire contract says.

In the MVP these sources are represented by **synthetic mock wire fixtures** (NewsML-G2, NITF, ninjs, plain text) with
`synthetic=true`. They are registered twice, each time with the configured flags applied:

- `mock_wire_gated` is attested with the most restrictive flags. It shows that the gate holds and that no hosted AI call is made.
- `mock_wire_demo` uses attested example flags that allow hosted AI. It shows the AI path on wire-format input.

**The initial public set** is listed with flags in [`specification/mvp-specification.md`](../../specification/mvp-specification.md) §6 (27 sources: 5 clean-core
rows including the GDELT file stream, 8 EN, 6 KO, 8 China-desk rows of which 6 are Chinese-language). Excluded: SBS (terms forbid reuse and AI training),
Reuters, AP, MBC, Reddit, state.gov (403), korea.kr (discontinued), Naver/NYT/NewsAPI/Guardian API/DART/YouTube Data
(BLOCKED-no-key), BIGKinds (reproduction prohibited), Bluesky/Mastodon (terms UNVERIFIED, person-centric PII risk, DR-9).

### Resolved conflicts

- **YouTube channel RSS: excluded from the MVP.** The robots rule wins (R5, VERIFIED) and there is no authorised keyless
  alternative. The authorised path is the YouTube Data API with a key the operator would have to obtain, under the 30-day cache
  rule and no video storage (DR-10). R8's single fetch is recorded as an out-of-scope finding in S1's report, not reused.
- **GDELT:** used for EN context and spike baselines via the 15-minute `lastupdate` file stream, cited as GDELT requires;
  never load-bearing for KO or ZH coverage.
- **AP/Reuters:** a later `licensed_wire` adapter kind, enabled only when the customer brings the licence
  (`licence_owner=tenant`, credentials in the tenant's own secret store, DR-15; `08_LEGAL…` §9(b)). Superdesk's AGPL AP Media
  client is a reference for that adapter, not code to copy ([`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) F-C-04).
- **R7's AI-off view vs DR-3:** R7's degradation table shows "original title and lead" when AI is off
  ([`technology/ai-and-agent-integration-report.md`](../../technology/ai-and-agent-integration-report.md) §4). DR-3 wins: the lead (feed summary) is shown only where `display ≥ snippet`;
  otherwise AI-off items show title + link + "AI 처리 대기".

## Consequences

- The desk assistant runs on free sources in private use; in internal (organisational) use it runs on sources whose terms
  are not non-commercial-only, plus anything the organisation licenses. This is a smaller feed set until the 12 unread
  publisher terms are read (open question OQ-2 in deliverable 12).
- The AP/Reuters core of the real seat is not reachable until a customer brings a licence; deliverable 09 states this.
- Every UI, API, MCP and digest renderer must call one `DisplayPolicy` function; enforcement in one place is testable.

## Evidence

[`sources-and-licensing/information-source-and-api-registry.md`](../../sources-and-licensing/information-source-and-api-registry.md) (§1, §2, F-D-01…06) · [`sources-and-licensing/source-registry.csv`](../../sources-and-licensing/source-registry.csv) ·
[`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) (F-L-01, F-L-02, F-L-05, §5, §6, DR-1…DR-15, §9(b)) ·
[`sources-and-licensing/acquisition-methods.md`](../../sources-and-licensing/acquisition-methods.md) · [`experiments/multimedia/results.md`](../../experiments/multimedia/results.md) §6.

## Reversal triggers

- A Korean lawyer's opinion that internal organisational use of "personal" feeds is acceptable (or not) → change
  `allowed_contexts` per source, no code change.
- The 12 unread publisher terms are read (OQ-2) → update flags.
- The operator obtains a YouTube Data API key and D7 is revisited → add a `youtube_api` metadata adapter with a 30-day purge.
- A customer supplies an AP or Reuters contract → build the `licensed_wire` adapter.
