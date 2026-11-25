# Adjacent applications (workstream M, R2, 2026-11-25)

> **Status: Estimate.** Desk-based; no dedicated search was run per domain. Per-row evidence tags apply.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Purpose:** architecture choices that do not block reuse. Not new MVP scope. **Evidence basis:** INFERRED throughout, from the product
rows in [`business/commercial-products.csv`](commercial-products.csv) (Meltwater, AISURFER, Factiva, Nexis, Dataminr, Feedly, GDELT, Event Registry) and
the desk-seat description in an analysis of public job advertisements. No dedicated search was run per domain, so each cell
is a design inference, not a surveyed fact. Dated 2026-11-25.

## 1 · Common infrastructure (identical across every domain)

| Layer | What it is | Why it is common |
|---|---|---|
| Collectors | RSS/Atom, HTTP fetch, licensed-feed adapters, file drop | Every domain reads feeds and pages; only the list differs |
| Item store | Normalised item: id, source, URL, title, text, language, timestamps, licence tier, fetch status | One schema carries every domain |
| Dedup and clustering | Exact-hash, near-duplicate, event grouping | Syndicated copies exist everywhere (Event Registry, GDELT show the pattern) |
| Query profile engine | Keyword and Boolean sets, media sets, owners, recipients | The unit of work in Meltwater, AISURFER, Factiva |
| Scoring and alert rules | Threshold, spike over baseline, watchlist hit | Same engine, different thresholds |
| Delivery | Digest schedule, urgent alert, queue UI, API, with delivery receipts | AISURFER Brief pattern |
| Human review gate | Draft then release | Needed wherever a wrong summary is costly |
| Audit and provenance | Source, fetch time, model version, licence flag per item | Needed for regulatory and compliance domains most |
| Health monitoring | Feed up/down, lag, volume anomaly | Generalises the seat duty "tell the wire or engineering when a feed breaks" |

## 2 · Domain configuration (what differs)

| Domain | Typical sources | Taxonomy | Entity lists | Alert rules | Notable constraint |
|---|---|---|---|---|---|
| Foreign-news desk (the MVP candidate) | AP/Reuters (licensed), public RSS, foreign outlets | Region, topic, urgency | Countries, leaders, orgs | Breaking, named-person, region surge | Wire licence limits redistribution and AI use |
| Corporate media intelligence / PR monitoring | Domestic press, online news, social | Company, brand, product, sentiment | Own brand, competitors, executives | Negative-coverage surge, executive mention | Korean press licence tiers (see 02) |
| Regulatory intelligence | Official gazettes, agency notices, law databases (e.g. law.go.kr), consultation pages | Agency, statute, status (draft, in force) | Statutes, agencies, regulated terms | New amendment, comment deadline | Authoritative-source dating matters; citations must be exact |
| Trade and sanctions / export control | Sanction lists, customs notices, ministry announcements, press | Programme, jurisdiction, commodity code | Sanctioned persons, vessels, HS codes | List change, new designation | False negatives costly; list matching is exact plus fuzzy-name |
| Supply chain | Port, weather, logistics, supplier news | Supplier, region, risk type | Suppliers, facilities, routes | Disruption near a facility | Geotagging needed (Dataminr geo-radius pattern) |
| Local government | Council minutes, notices, procurement postings, local press | Agency, programme, location | Departments, officials, contractors | New notice matching a topic | Many small non-standard sources; scraping fragility |
| Financial and economic | Wires, filings, statistics releases, central-bank notices | Company, sector, indicator | Tickers, issuers | Earnings, data release, guidance change | Latency, licence cost (Factiva, Reuters) |
| Geopolitical | Foreign press, government statements, GDELT | Region, actor, event type | Actors, regions | Event escalation | Translation and source bias |
| Competitive intelligence | Competitor sites, job posts, press releases, patents | Competitor, product, move type | Competitors, products | Page change, launch, hiring signal | Page-change detection is a different collector |
| Public-sector research | Academic, agency reports, government data | Policy area, evidence type | Programmes, institutions | New report on a topic | Citation and archive needs; low urgency |

## 3 · Design rules that follow (to keep reuse open)

1. **Make query profiles, entity lists and taxonomies data, not code.** A profile file per domain; no domain terms in the engine.
2. **Keep the item schema domain-neutral** with a free `attributes` field for domain data (tickers, HS codes, statute ids).
3. **Treat page-change detection and feed polling as two collector types** behind one interface, because competitive and local-government work needs the first.
4. **Put the licence tier and permitted-use flag on the item,** so a domain with a stricter licence (wires, sanctions databases) cannot leak into a looser one.
5. **Make alert rules pluggable** (keyword, spike, watchlist, exact-list change) rather than one threshold.
6. **Keep AI steps optional per step** with a rules-based fallback, since some domains (compliance, sanctions) require reproducible, auditable output.
7. **Do not build** multi-tenant accounts, billing or per-client branding in round 1: no adjacent domain needs them for a pilot (INFERRED).

## 4 · What this does not establish

No domain was researched on its own; sources and rule examples are design inference. A control-checked survey of any single domain would
be a round-2 offer, and none is likely to change D1–D8.
