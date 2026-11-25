# ADR-003 · MVP user and use case (D3): a foreign-news desk assistant, sold as software that processes content the customer already licenses (Model B)

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: Model B built.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25). Revised the same day for project-owner supplement 02
  (a private requirements note).
- **Informs:** deliverable 12 §1–§2, deliverable 09 (coverage), ADR-008, ADR-010.

## Context

### Two use cases on one pipeline

Both candidate use cases run the same pipeline (collect → dedup → select → summarise/translate → deliver). They differ in
trigger, surface and quality target ([`business/industry-and-business-process-report.md`](../../business/industry-and-business-process-report.md) §1).

| | Foreign-news desk assistant | Client clipping / monitoring service |
|---|---|---|
| Trigger | An event (flash), plus the shift rhythm | The clock (조간 from 04:00, 석간 from 12:40; F-A-04) |
| Surface | A persistent queue and an immediate notice (F-A-02) | A bundled morning or evening file, reviewed before it is sent (F-A-05) |
| Quality target | Precision on "important" (≈80:1 triage, F-A-03) | Recall on "mentions us" |
| Market | Least served commercially ([`business/commercial-product-landscape.md`](../../business/commercial-product-landscape.md) §1 point 4, §5) | Served by AISURFER and 스크랩마스터, sold with licence tiers (F-B-03) |
| Inputs | The seat's own wires (AP/APTN, Reuters, 연합뉴스), which the broadcaster licenses, plus public feeds | Korean press content, which needs news-copyright licences |

### Two commercial models (supplement 02)

| | **Model A**: the provider acquires, processes and distributes content | **Model B**: the provider supplies software that processes content the customer licenses itself |
|---|---|---|
| Who holds the content licence | The provider | The customer (broadcaster) |
| Legal exposure | The provider redistributes third-party content to clients and needs its own redistribution licences from every rightholder (`08_LEGAL…` §0 D3, F-L-01, F-L-03 AP v. Meltwater, §13.0) | The provider holds no rights in the content and acts as the licensee's processor. Acquisition moves to the customer's authorised channel. A licence cannot be assigned without consent (저작권법 §46(3), V), so the licence stays with the customer. **Whether Model B works for a given customer is decided by what that customer's contract says** about service providers, storage, AI processing and recipients (`08_LEGAL…` §13.0, §13.2: "the single question that decides whether Model B works for a given customer"). Korean broadcasters' AP, Reuters and 연합뉴스 contracts are not public (U-abs). The terms may permit or restrict any of these, and nothing here assumes either |
| Fit to the seats | The clipping seats (W5) | The 외신 seats (W1, W2). Their duties name AP, APTN and Reuters (`responsibilities.csv` R-01, R-02; `02_COMMERCIAL…` §8.1 E-C) |
| Market evidence | Crowded. AISURFER and 스크랩마스터 are the model (F-B-03, §8.2) | No incumbent found for foreign-wire desk triage (UNVERIFIED-absent, §8.2). AP Media Agent is a customer-run tool that writes standard files to folders the customer's systems watch (VERIFIED, `02_COMMERCIAL…` §8.1). The Arirang ₩888,030,000 APTN contract cited in the supplement was **not located** (six searches, E-B). Buyer existence is INFERRED from job descriptions |
| Testable here | No (no Korean press licence) | Yes. Mock wire fixtures and local files go through the generic connector interface (ADR-010), alongside public feeds |

R9's and R2's Model-B sections (`08_LEGAL…` §13, including DR-16…DR-30; `02_COMMERCIAL…` §8;
[`business/broadcaster-licensing-evidence.md`](../../business/broadcaster-licensing-evidence.md)) were on disk before this ADR was finalised, and the
ADR rests on them. The APA (Austria) terms quoted in §13.2 are one published example. They are **not** treated as typical
of, or evidence about, Korean broadcasters' contracts (§13.2 scope note).

### Limits on the evidence

- The desk's unmet need is seen through job ads, not interviews (R1 §6, R2 §1).
- About half of the 외신 seat is video, ingest or feed-fault work that a text MVP cannot reach (F-A-01).
- The person using the desk tool is a contract monitor, not a buyer (F-A-08). Under Model B the buyer is the broadcaster.

## Options considered

1. A desk assistant under Model B, with clipping (Model A) deferred.
2. A desk assistant on public feeds only (the first draft of this ADR).
3. Clipping first (Model A).
4. Both in the MVP.

## Decision

**Option 1.** The MVP is information-processing software for **one foreign-news desk inside one organisation that brings
its own content licences**. The organisation is single-tenant: one deployment per customer (ADR-009).

- **Demonstrated without paid access.** The MVP runs on two kinds of input. The first is mock newswire data and
  representative local files: NewsML-G2, NITF, ninjs and plain-text wire fixtures dropped into a watched inbox directory, which
  stands in for AP Media Agent output. The second is the free public feeds of ADR-002. Both enter through the generic
  connector interface (ADR-010).
- **Use contexts.** In round 2 the system runs in `use_context=private` (the researcher acting as a monitor). In a pilot it
  runs as `internal` inside a broadcaster, where licensed sources carry `licence_owner=tenant`.
- **What the user does.** The monitor:
  - watches wire and public foreign-news text;
  - works from a deduplicated, event-grouped, ranked queue (Korean summaries only when AI mode O2 is enabled and the source's flags allow it);
  - gets a notice for flash items;
  - registers important items with a note;
  - searches the archive;
  - sends a reviewed shift handoff or morning briefing.
- **Model A (clipping and redistribution to third parties) is deferred.** It needs the provider's own content licences.
  Nothing in the design blocks adding it later: profiles, schedules, recipients and the draft-review-send digest are
  generic ([`business/adjacent-applications.md`](../../business/adjacent-applications.md) §3).
- **Licence behaviour is customer-set configuration.** At onboarding, the customer enters its own contract's terms as
  source flags: storage days, display scope, permitted processing, third-party processors, external AI, recipients. The
  checklist used is DR-30 / DR-17 (`08_LEGAL…` §13.5), and the person who enters the terms attests to them.
- **Defaults for unconfigured sources.** An unconfigured customer-licensed source runs with safe-by-default values:
  `external_ai_allowed=false`, `redistribution=none`, and no ingestion until attested. These defaults are a choice for an
  unconfigured source. They are **not** a claim about what any contract says.

## Consequences

- The real seat's main input becomes reachable in a pilot without the provider ever holding the content: through a
  directory watcher on the customer's AP Media Agent output, or through a customer-credentialed API connector (designed,
  deferred).
- With `external_ai_allowed=false`, licensed items get no hosted-LLM summary. They are still collected, deduplicated,
  clustered by TF-IDF, searchable and alertable by rules. They get AI summaries only if the customer's contract allows
  hosted AI (and the customer sets the flag) or the customer supplies its own endpoint (ADR-006). The system is fully
  functional in deterministic mode O1 regardless (ADR-006). How much AI value a given customer gets depends on that
  customer's contract (OQ-1).
- Deliverable 09 marks every video, footage-ingest, footage-archive and video-feed-fault duty OUT, and gives the reason.
  It maps the AP, APTN and Reuters text duties to the wire connectors.

## Evidence

- [`business/industry-and-business-process-report.md`](../../business/industry-and-business-process-report.md) F-A-01…F-A-08
- [`business/commercial-product-landscape.md`](../../business/commercial-product-landscape.md) §1, §5, F-B-01, F-B-03
- [`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §0, §6, §9(b), §9(c)
- [`sources-and-licensing/information-source-and-api-registry.md`](../../sources-and-licensing/information-source-and-api-registry.md) §1 "Consequence for D3"
- [`business/desk-responsibilities.csv`](../../business/desk-responsibilities.csv)
- [`sources-and-licensing/legal-and-licensing-report.md`](../../sources-and-licensing/legal-and-licensing-report.md) §13 (DR-16…DR-30) · [`business/commercial-product-landscape.md`](../../business/commercial-product-landscape.md) §8 · [`business/broadcaster-licensing-evidence.md`](../../business/broadcaster-licensing-evidence.md)
- Supplement 02

## Reversal triggers

- A pilot customer's contract bars third-party processing of its wire content. For that customer, Model B then works
  only as customer-hosted (CH) software that the provider never touches (`08_LEGAL…` §13.1, CH row), running in O1 mode
  or with a customer-run AI endpoint.
- A Korean press licensing route and a paying clipping client appear. Model A would then be added as a second profile,
  under DR-6 tenant isolation.
- Desk interviews in round 2 show that monitors do not want a queue, or that the text half of the seat is not where their
  time goes.
