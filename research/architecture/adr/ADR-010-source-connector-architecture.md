# ADR-010 · Source connector architecture: one ingestion contract for public feeds, customer-licensed wires, local files and newsroom systems

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: RSS/Atom and directory-watcher connectors built; API connectors deferred.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Source requirement:** project-owner supplement 02
  (a private requirements note, read in full);
  decision log P-007; the project owner's correction on contract terms (2026-11-25).
- **Informs:**
  - deliverable 11 §3, "Source connector architecture";
  - deliverable 12, FR-27…FR-31;
  - deliverable 09, rows R-01, R-02, R-12, R-18…R-21 and R-25.

## Context

**Who the customer is.** The target segment includes broadcasters that already license AP/APTN, Reuters and 연합뉴스. The
외신 seat duties name AP, APTN and Reuters (`responsibilities.csv` R-01, R-02, R-12). Under **Model B** the product is
software that processes content the customer licenses (ADR-003).

**AP Media Agent and the AP Media API** (VERIFIED by R2 from AP's documentation, [`business/commercial-product-landscape.md`](../../business/commercial-product-landscape.md) §8.1,
[`business/broadcaster-licensing-evidence.md`](../../business/broadcaster-licensing-evidence.md) E-A1…E-A18):

- **Media Agent** is a Java application the customer runs with its own API key.
- It writes files and metadata to folders that the customer's CMS watches.
- Formats: **NewsML-G2 XML or JSON** item metadata, **NITF** text (story, caption, script, shotlist, timecoded transcript)
  and media renditions.
- Layout: folders per entitlement or per version, files named `ItemID--Version--ContentID`, a 24-hour duplicate filter and
  optional auto-delete. Look-back is 72 hours.
- **The Media API** uses the customer's key in `x-api-key`. It offers feed, search, item, on-demand and RSS endpoints, plus
  `/account/plans` and `/account/quotas`, and holds 30 days of content. Rate-limit numbers are account-specific and were
  not found.

**Other wires.** Reuters Connect and 연합뉴스 delivery mechanisms and terms are **UNVERIFIED-absent**
([`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §13.4, §13.6).

**Reference code.** Superdesk contains an AP Media API client and parsers for ANPA, NewsML 1.2/2.0, NITF, IPTC 7901 and
ninjs (VERIFIED code read, AGPL-3.0, [`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) F-C-04).

**Legal framing** (`08_LEGAL…` §13):

- The provider must stay a processor acting for the licensee.
- Ingestion should be tenant-initiated (DR-26).
- There must be no cross-customer reuse of content (DR-19).
- Licence flags are set by the customer with attestation (DR-17), using the onboarding checklist (DR-30).
- `external_ai_allowed=false` is the default for tenant sources (DR-18).
- Korean broadcasters' wire contracts are not public. **The APA (Austria) terms in §13.2 are one example, not a
  description of those contracts** (§13.2 scope note). What a given customer's contract allows is entered by that customer.

## Options considered

1. **Source-specific ingestion code per vendor.** Fast for one source, but every new source touches the pipeline.
2. **One connector contract** that produces a normalised, ninjs-style item carrying provenance and a snapshot of the
   licence flags, with connector kinds as plug-ins. **Chosen.**
3. **Adopt Superdesk ingest.** It needs MongoDB, Elasticsearch, Redis and Celery, and it is AGPL (ADR-001).

## Decision

### 1. The connector contract

```python
class Connector(Protocol):
    kind: str                                    # 'feed' | 'http_api' | 'directory' | 'wire_api' | 'nrcs_inbound'
    def poll(self, cursor: Cursor | None) -> PollResult        # new RawUnits + next cursor + status (never raises on remote failure)
    def parse(self, raw: RawUnit) -> list[NormalisedItem]      # pure, deterministic, fixture-testable
    def health(self) -> ConnectorHealth                         # last_success, error_streak, last_error_class
```

**`PollResult`**

- It always carries an explicit status: `ok`, `not_modified`, `empty` or `error:<class>`. "0 items" is therefore never
  read as "no news" ([`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) F-C-02).
- Each poll writes a `fetch_run` row.

**`NormalisedItem`**

- Fields use ninjs-style names:

  | Field | Meaning |
  |---|---|
  | `uri` | The source's own id. For AP files this is the ItemID |
  | `type` | text, video, audio or picture |
  | `version` | Version number. For AP files this comes from the filename or the metadata |
  | `firstcreated`, `versioncreated` | Creation timestamps |
  | `pubstatus` | usable, withheld or canceled |
  | `headline`, `slugline`, `byline` | Text identifiers |
  | `located` | Place of the story |
  | `language`, `urgency` | |
  | `description_text` | Summary or lead |
  | `body_text` | Full text |
  | `subjects` | Subject codes |
  | `renditions[]` | Media renditions |
  | `usageterms`, `restrictions` | Rights fields |
  | `embargoed` | Embargo time |
  | `associations` | Linked items, e.g. a script or shotlist that belongs to a clip |

- Provenance travels with each item: `source_id`, `connector_kind`, `raw_ref`, `raw_sha256`, `parser`, `received_utc`,
  `synthetic`, and `licence_snapshot` (the source's flags at ingest time).
- After parsing, every item takes the same path: licence gate, normalise, dedup, cluster, optional AI, rules, delivery.
  Nothing downstream branches on connector kind.

### 2. Connector kinds

| Kind | What it reads | MVP status | Notes |
|---|---|---|---|
| `feed` | RSS/Atom over HTTP (feedparser 6.0.14 + httpx 0.28.1) | **Implement** | Conditional GET; RFC 9309 robots matcher; descriptive UA; per-host serialisation; connect-time SSRF guard |
| `http_api` | Keyless JSON APIs (Federal Register, SEC, GDELT `lastupdate` files) | **Implement** | Same safeguards as `feed` |
| `directory` | A customer-authorised inbox: AP Media Agent output and equivalent vendor ingest folders | **Implement**, demonstrated with synthetic fixtures | §3 |
| `wire_api` | The customer's own key to AP Media API (`x-api-key`; feed, item, entitlements and quota endpoints) or Reuters Connect | **Designed, deferred** | Built when a customer provides a contract and a key. Read `/account/plans` and `/account/quotas` before polling. Superdesk's `ap_media.py` is a reference: read it, do not copy it (AGPL). Reuters is UNVERIFIED |
| `nrcs_inbound` | Items pushed by a newsroom system, MAM or CMS, via an export directory or a webhook | **Designed, deferred** | Directory exports already work through `directory`. AP lists an ENPS/Storytelling API (E-A18), not examined. MOS deferred |
| `changedetection`, `rsshub` | Sidecar services for pages with no feed (ADR-001) | **Designed, off** | — |

### 3. The directory watcher

**Read-only, inside a root**

- One configured root is set per source.
- The watcher resolves real paths. It refuses symlink escapes and files over a size limit.
- It never moves, renames or deletes customer files.
- Media Agent can auto-delete its own output. The watcher therefore ingests promptly (default scan interval 30 s) and
  records a missing file as `gone`. A missing file is not an error.

**Polling scan**

- The watcher scans on a timer. It does not rely on OS file events.
- A file is ingested once its size and modification time have been stable for N seconds (default 10).
- The ledger key is `(relative_path, size, mtime_ns, sha256)`.
- The AP-style name `ItemID--Version--ContentID` is parsed when present. A higher version of the same ItemID becomes a
  new revision of that item.
- Media Agent's own 24-hour duplicate filter is not relied on, because our dedup is content-based.

**Format detection by content, not extension**

| Content | Handled as |
|---|---|
| XML in the IPTC G2 namespace (`newsMessage` / `newsItem`) | NewsML-G2 |
| XML with an `nitf` root | NITF. Story, caption, script, shotlist and transcript blocks map to `body_text` or associations |
| JSON with ninjs keys, or AP's NewsML-G2-as-JSON metadata | ninjs (or a JSON mapping table) |
| Text with a header block (`SLUG:`, `HEADLINE:`, `DATELINE:`, `URGENCY:`, `BODY:`), a project-defined mock format | Plain-text wire |
| Media files, detected by magic bytes | `media_asset` only, linked to the sidecar that names them |
| Anything else | Quarantined, with a reason |

**Safe parsing**

- XML is parsed with entity expansion and external DTDs disabled, using `defusedxml` (pin and verify at build).
- Files are treated as data and never executed.

**Footage**

- Footage is recorded only: path, sha256 and size, plus duration and format taken from the sidecar.
- It is not copied, transcoded or served (ADR-007).

### 4. Licence flags: customer-set, reflecting the customer's own contract

**Onboarding step (FR-30).** Before any real customer-licensed source is enabled, an admin of the customer enters that
customer's contract terms as source flags and attests to them. The checklist is DR-30: licence holder; automated
processing, classification, summarisation and translation; storage limit; service providers and processors; AI
processing, by vendor and region; authorised users; recipients outside the licensee; audit and deletion. The system stores
`attested_by`, `attested_on`, `agreement_ref` and `valid_until`. Ingestion stops automatically after `valid_until`
(DR-27). The system makes no assumption about what a contract permits. Every behaviour below comes from these flags.

The schema keeps R9's DR-1 names. Supplement 02's names and R9's DR-17 fields map onto them as follows:

| Supplement 02 / DR-17 name | Stored as | Behaviour |
|---|---|---|
| `store_full_text`, `storage_days` | `storage` (none / metadata / transient / full) + `retention_days` | Body kept, or derived and then discarded (DR-4). Purge after `retention_days` with a receipt (DR-21) |
| `display_full_text`, `display_scope` | `display` (none / headline / snippet / full) | One `DisplayPolicy` serves UI, API, MCP, digest and export (DR-3) |
| `ai_processing_allowed`; `classification`, `summarisation`, `translation` | `ai_processing` (yes / no / unknown) + `permitted_ops` (JSON set of `classify`, `summarise`, `translate`, `embed`) | An AI capability runs on an item only if its op is permitted |
| `external_ai_allowed` | `external_ai_allowed` (bool) | `false` means only a customer-hosted endpoint may receive the text; if there is none, the item takes the O1 path |
| `third_party_processors_allowed` | same name (bool) | `false` for a tenant source means the provider must not operate the instance (MP/SaaS). Allowed only in CH (`08_LEGAL…` §13.1) |
| `redistribution`, `internal_only`, `authorised_user_scope` | `redistribution` (none / internal / external) + `authorised_users` (list or role) | Gates digest recipients, export and outbound integrations (DR-25) |
| `licence_holder`, `agreement_ref`, `valid_until`, `territory`, `attested_by`, `attested_on` | same names | Audit (DR-20), kill switch (DR-27) |
| `synthetic` | same name | Marks project-made fixtures. **S1 still applies the configured flags to synthetic sources**, which is stricter than DR-17's bypass, so that the gate itself can be demonstrated |

**Safe-by-default values for an *unconfigured* tenant source.** These are a choice that keeps the system safe until the
customer has entered its terms. They are **not a statement about what AP, Reuters or 연합뉴스 contracts contain**:

| Flag | Default |
|---|---|
| Ingestion | Disabled until attested |
| `external_ai_allowed` | false (DR-18) |
| `third_party_processors_allowed` | false |
| `redistribution` | none |
| `permitted_ops` | empty (O1 only) |
| `retention_days` | Required. No default; onboarding asks for the contract's figure |

### 5. Credentials

- Customer-provided credentials (wire API keys, NRCS webhook secrets) are read only through the ADR-009 `SecretStore`
  (`owner=customer`).
- They are scoped to the instance. They are never logged, stored in the DB or returned by any API (DR-15, DR-22, M12).
- The provider never logs in to a wire with its own account (DR-24).

### 6. AI provider abstraction

Defined in ADR-006 §5:

- `anthropic_api` and `openai_embeddings_api`: hosted, in the MVP.
- `customer_hosted`: an endpoint inside the customer's own account or region (for example in-region inference in Seoul,
  which is DOCUMENTED but whose region availability is unverified, `08_LEGAL…` §13.3), or customer-run models on
  customer hardware. This is **design only**. Nothing runs locally on this workstation, per the no-local-inference policy.

### 7. Newsroom system integration points (outbound first)

1. **File export of registered items** (ninjs JSON plus plain text) to a configured drop directory that an NRCS or CMS
   watches. SHOULD, in post-MVP slice 1.
2. **Webhook**, HMAC-signed with a customer secret. Deferred.
3. **Inbound** from MAM or NRCS exports through `directory`.
4. **MOS and BXF.** Deferred.

All outbound integrations obey `redistribution` and `authorised_users`.

### 8. MVP demonstration without paid wire access

The fixtures are synthetic text written for the project, with `synthetic=true`, kept in `tests/fixtures/wire/`:

| Format | At least | Must include |
|---|---|---|
| NewsML-G2 | 5 items | One version update and one `pubstatus=canceled` kill |
| NITF | 3 items | One with a shotlist block |
| ninjs | 5 items | One `type=video` item with a rendition and an AP-style `ItemID--Version--ContentID` name |
| Plain-text wire | 5 items | One `URGENCY: 1` flash and one Korean item |

They also include:

- one malformed file per format;
- one symlink pointing outside the root;
- one cross-format near-duplicate pair.

The fixtures are dropped into a watched inbox next to the live public feeds. Two source registrations show both paths:

- `mock_wire_gated` is attested by the fixture loader with the most restrictive flags: `external_ai_allowed=false`, empty `permitted_ops`, `redistribution=none` and `retention_days=7`. It shows that the gate works and that no hosted AI call is made.
- `mock_wire_demo` carries attested example flags that allow hosted AI. It shows the AI path on wire-format input.

## Model A delta (added after review V1-08, 2026-11-25)

This ADR designs for **Model B**: the customer licenses the content and owns the credentials, and the software processes
it. **Model A**, where the provider acquires and distributes content, is deferred (ADR-003, DR-29). Moving to Model A
would change:

| Area | Model B (MVP) | Model A would need |
|---|---|---|
| Credentials | Customer-owned (`owner=customer`) through `SecretStore` | Provider-owned wire and clipping accounts (`owner=provider`), with the provider as licensee |
| Licence flags | Entered and attested by the customer per their contract (FR-30) | Set by the provider from its own redistribution licence (e.g. a 한국언론진흥재단 clipping licence), per customer tier |
| Collection | Isolated per instance (NFR-24) | Possibly shared collection fanned out to customers (an ADR-009 DEFER item) |
| Output | Internal users only by default; redistribution gated | Redistribution to client recipients is the product, so recipient entitlements and usage reporting to rightholders are needed |
| Gate | DR-29 blocks Model A behaviour | DR-29 relaxed only with a licence on file |

The connector contract, the parsers, `LicenceGate` and `DisplayPolicy` are the same code in both models. Only
configuration, credential ownership and the redistribution path differ. No MVP code needs to change to keep Model A
possible.

## Consequences

- Adding AP (watched Media Agent folder or `wire_api`), Reuters or a 연합뉴스 feed means one connector plus one source
  row, with the customer's attested flags. The pipeline does not change.
- Under any contract, the deterministic O1 path delivers the full desk workflow.
- How much AI a customer gets is set by that customer's contract and configuration.
- The real Media Agent output of a pilot customer is still untested. The first pilot task is to point the watcher at a
  sample of it.

## Evidence

- [`business/commercial-product-landscape.md`](../../business/commercial-product-landscape.md) F-B-01, §8.1, §8.2
- [`business/broadcaster-licensing-evidence.md`](../../business/broadcaster-licensing-evidence.md) (E-A1…E-A18)
- [`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §9(b), §9(c), §13.0–§13.5 (DR-16…DR-30)
- [`technology/open-source-applications-evaluation.md`](../../technology/open-source-applications-evaluation.md) F-C-02, F-C-04
- [`technology/multimedia-and-broadcast-report.md`](../../technology/multimedia-and-broadcast-report.md) §2–§3
- [`sources-and-licensing/acquisition-methods.md`](../../sources-and-licensing/acquisition-methods.md)
- `responsibilities.csv`
- Supplement 02

## Reversal triggers

- A pilot customer's Media Agent output differs from the documented layout. Add a parser variant; the contract stays.
- A customer's contract bars third-party processors. Deploy customer-hosted only for that customer
  (`third_party_processors_allowed=false`).
- A pilot NRCS accepts only MOS. Bring MOS forward.
