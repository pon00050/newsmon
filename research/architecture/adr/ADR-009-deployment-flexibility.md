# ADR-009 · Deployment flexibility: what the single-tenant MVP decides now, and what it defers

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: Single-tenant seams kept; not separately verified.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Source requirement:** a private requirements note (read in
  full); decision log P-005. Legal inputs: [`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §9(a)–(d), DR-6, DR-14, DR-15;
  [`sources-and-licensing/oss-licenses.csv`](../../sources-and-licensing/oss-licenses.csv).
- **Informs:** deliverable 11 §10 "Deployment models", deliverable 12 §11 "Deployment flexibility constraints" (NFR-20…NFR-31).

## Context

The supplement defines three future models on one codebase: **CH** customer-hosted, **MP** managed private (dedicated
infrastructure the provider operates), **SaaS** provider-hosted. The MVP must stay **lightweight, single-tenant and
independently deployable**, with no billing, enterprise SSO, multi-tenancy or licence enforcement unless indispensable.
This machine has **no Docker** ([`decision-log.md`](../../decision-log.md) P-004): containerisation can be specified, not tested here.

## Why "one instance per customer" (siloed) is the bridge

A siloed deployment runs the **same artefact as the MVP**, once per customer, with its own data directory, database file,
configuration and secrets. That makes models CH and MP a question of **who operates the instance**, not of code:
- **Isolation is physical.** Customer A's licensed wire content (DR-6) and credentials (DR-15) never share a process,
  file or index with customer B, which is exactly what BYOL wire licences and R9's §9(b) checklist require.
- **PIPA roles stay clean.** In CH the customer is the 처리자; in MP the provider is a 수탁자 for one customer per instance
  (`08_LEGAL…` §9(d)); hosting region and AI provider are per-instance settings.
- **AGPL posture is simple.** The core links no AGPL/SSPL/fair-code code; optional AGPL services (RSSHub) run unmodified in
  separate processes, so shipping an image (CH) or operating it (MP) adds only notice/SBOM duties (`08_LEGAL…` §9(a)).
- **No tenancy code is needed** while there is one customer per instance; the `workspace_id` column (below) is a seam, not
  a feature.

**What SaaS would additionally need** (all DEFER): multi-tenant enforcement in every query (or Postgres row-level
security), a move to PostgreSQL (R6 trigger 3), tenant-aware authn/authz with SSO, a per-tenant secret vault, shared
collection of public sources with isolated licensed content, entitlement and usage metering, billing, provider operations
(on-call, incident handling, per-tenant backups), a §26 entrustment and sub-processor list as product features, AI Basic Act
§31 notice/labelling to every user and possibly a 국내대리인 (§36), cross-border handling of personal data (§28-8), and an
AGPL §13 review if any AGPL component was modified.

## Decisions by topic

Cost estimates for deferred items are INFERRED (S1 engineering judgement, no measurement); they assume the DECIDE-NOW
items are in place.

| # | Topic (supplement) | Class | MVP decision, or deferral trigger and rough cost |
|---|---|---|---|
| 1 | Deployment portability and containerisation | **DECIDE-NOW** | 12-factor layout: all state under one `NEWSMON_DATA_DIR`; config from `NEWSMON_CONFIG_DIR` + environment; logs as JSON lines to stdout/stderr; no absolute Windows paths in code. Ship a **Dockerfile as an artefact, untested here (no Docker on this machine)**; the tested path is a Python venv on Windows and Linux. |
| 2 | Separation of application logic from infrastructure | **DECIDE-NOW** | Ports and adapters: `Repository`, `SearchIndex`, `SourceAdapter`/connectors, `AIProvider`, `Notifier`, `SecretStore`, `AuthProvider`, `Clock`. Domain code imports none of SQLite, httpx, anthropic or smtplib directly. |
| 3 | Configurable storage and database backends | **DECIDE-NOW** (seam) / DEFER (Postgres) | SQLite behind the repository layer; portable DDL subset (ADR-004). DB URL from env. **Postgres adapter deferred**; trigger: any R6 migration trigger or SaaS. Cost later: ~1–2 weeks (adapter + FTS replacement + data copy). Without the seam: a rewrite of every query. |
| 4 | Single-tenant vs multi-tenant | **DECIDE-NOW** (seam) / DEFER (multi-tenant) | One `workspace` row; every owned table carries `workspace_id NOT NULL` (default 1); the repository layer injects it into every query. **Multi-tenancy deferred**; trigger: SaaS decision. Cost later: ~2–4 weeks (enforcement tests, per-tenant config, admin) with the column; ~4–8 weeks without it (migration of every table and query). |
| 5 | Customer data isolation | **DECIDE-NOW** | Per-instance data dir and DB; no cross-instance shared index, cache or dedup store; licensed bodies never leave their instance except to an AI endpoint the flags allow (DR-6). |
| 6 | Authentication and authorisation | **DECIDE-NOW** (minimal) / DEFER (SSO) | `AuthProvider` interface; MVP implementations: `local` (bind 127.0.0.1, single user) and `static_users` (users file with stdlib `hashlib.scrypt` hashes, session cookie); roles `viewer`, `editor`, `admin` stored on `app_user`; API and MCP tokens stored hashed with scopes (`news.read`). **SSO/OIDC/SAML deferred**; trigger: a customer IdP requirement. Cost later: ~1 week behind the interface. |
| 7 | Customer-specific monitoring configuration | **DECIDE-NOW** | Profiles, rules, schedules, recipients and the source registry are **data** (YAML files in the config dir, imported to DB rows, editable in the UI and exportable); no customer term in code ([`business/adjacent-applications.md`](../../business/adjacent-applications.md) §3 rule 1). |
| 8 | Customer-provided vs provider-managed API credentials | **DECIDE-NOW** | One `SecretStore` interface: `get(name, workspace_id)`. MVP backend: environment variables / `.env` in the instance (never logged, never in DB, never returned by API/MCP, M12). Credentials are tagged `owner=customer|provider`. Anthropic/OpenAI terms: a provider key powering a value-added application is allowed; BYOK is silent (Anthropic) or at risk on a literal reading (OpenAI §3.3(g)) (`08_LEGAL…` §9(c)). **Encrypted vault backend deferred**; trigger: MP/SaaS. Cost later: days. |
| 9 | Customer-owned licensed information sources | **DECIDE-NOW** | Connector contract + licence flags (ADR-010): `licence_owner=tenant`, `external_ai_allowed=false` default, `redistribution=none`, `retention_days`; customer credentials only via `SecretStore`; the customer enters **its own contract's terms** as flags at onboarding, using the DR-30 checklist, with attestation fields (DR-17: `licence_holder`, `agreement_ref`, `valid_until`, `attested_by`, `attested_on`) and `third_party_processors_allowed` (ADR-010 §4). There is a `valid_until` kill switch (DR-27) and a purge with receipt on expiry (DR-21). The defaults for an unconfigured source are a safety choice, not a claim about contracts. |
| 10 | Shared vs isolated collection pipelines | **DECIDE-NOW: isolated** / DEFER shared | Each instance collects for itself. **Shared public-source collection deferred** (it would reduce load on publishers, DR-5, but couples tenants); trigger: SaaS with > ~10 tenants on the same public feeds. Cost later: ~2 weeks (a collector service publishing normalised public items to tenant pipelines; licensed sources stay per tenant). |
| 11 | Software licensing and entitlement management | **DEFER** | No licence keys, seat counts or feature flags tied to payment. Trigger: first paid CH distribution. Cost later: ~1 week for a signed licence file checked at start-up. Keep features behind config flags so entitlements can map onto them. |
| 12 | Configuration portability | **DECIDE-NOW** | `newsmon config export` / `import` round-trips sources, profiles, rules, schedules and recipients as YAML; secrets excluded by design; schema-versioned. |
| 13 | Automated installation and updates | **DECIDE-NOW** (minimal) / DEFER (auto-update) | Installation = `uv` venv + `pip install` of a pinned lock + `newsmon init`; DB migrations versioned and applied by `newsmon migrate` at start-up with a pre-migration backup. **Auto-update channel deferred**; trigger: more than a handful of CH installs. Cost later: ~1 week. |
| 14 | Backup, recovery and data export | **DECIDE-NOW** | Daily `VACUUM INTO` + integrity check + off-host copy (operator-configured path); `newsmon restore`; `newsmon export` = JSON Lines per table + the licence-flag table + a manifest with row counts, **excluding** text whose flags forbid export (only the tenant's own licensed content goes back to that tenant, `08_LEGAL…` §9(d)); deletion-on-exit command with a report. |
| 15 | Usage metering and resource allocation | **DECIDE-NOW** (record) / DEFER (meter) | Record what is already needed for operations: AI tokens and `cost_usd` per call, fetch bytes per run, daily spend cap. **Billing-grade metering deferred**; trigger: SaaS or usage-priced MP. Cost later: ~1 week (aggregation tables + export). |
| 16 | OSS licensing across deployment models | **DECIDE-NOW** | Core dependencies are permissive only (MIT/BSD/Apache/PSF/public domain; see deliverable 10). No AGPL/SSPL/fair-code (n8n) code imported into the core; AGPL tools only as unmodified separate services; no no-licence repos. SBOM (CycloneDX or SPDX, tool chosen at build) and `THIRD_PARTY_NOTICES` generated in CI from day one, including base-image packages if the Dockerfile is used (DR-14, `08_LEGAL…` §9(a)). EUPL-1.2 (Taranis) not used. |

## Consequences

- The MVP pays a small fixed cost (a `workspace_id` column, six interfaces, export/import commands, an SBOM step) to keep
  CH and MP open with no code change and SaaS open at a bounded cost.
- None of the DEFER items enters the MVP backlog (S2 brief item 4).

## Evidence

`SUPPLEMENT_01…` · [`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §7, §8 (DR-6, DR-9, DR-13, DR-14, DR-15), §9(a)–(d) ·
[`technology/data-model-and-lifecycle.md`](../../technology/data-model-and-lifecycle.md) §5 (migration triggers) · [`business/adjacent-applications.md`](../../business/adjacent-applications.md) §3 ·
[`decision-log.md`](../../decision-log.md) P-004, P-005.

## Reversal triggers

- A decision to launch SaaS before any CH/MP customer → bring forward topics 3, 4, 6, 8, 10, 15 (Postgres + tenancy first).
- A customer requires container-only delivery → test the Dockerfile on a Docker-capable host before shipping.
