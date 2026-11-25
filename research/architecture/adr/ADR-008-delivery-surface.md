# ADR-008 · Delivery surface (D8): editorial queue + flash notice + reviewed digest, with a read-only API and MCP server

> **Status: Historical decision.** Status in the decision log: PROPOSED. Build state: Review queue built; flash notice, digest, REST API and MCP deferred.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

- **Status:** PROPOSED (S1, 2026-11-25).
- **Informs:** FR-16…FR-26, [`specification/interface-spec.md`](../../specification/interface-spec.md).

## Context

- The desk report is a **system registration** ("PC등록") and the notice (고지) is a separate act → persistent queue +
  immediate notification (DOCUMENTED, `01_INDUSTRY…` F-A-02; [`business/desk-practices.md`](../../business/desk-practices.md) §1, §6).
- Incumbents keep a human between draft and recipient (AISURFER Brief: draft → staff review → send, delivery receipts)
  (`01_INDUSTRY…` F-A-05; `02_COMMERCIAL…` F-B-03, §4).
- Alerts are needed for two cases: a desk flash (minutes) and a crisis spike; vendors alert by email ([`business/desk-practices.md`](../../business/desk-practices.md) §6).
- Messenger delivery (KakaoTalk/Telegram/Slack) at Korean desks: UNVERIFIED-absent.
- API/MCP: no desk-practice evidence; R7 recommends a read-only MCP server so the user's own Claude client is the agent;
  R4 recommends `datasette-mcp` as the first MCP surface ([`technology/mcp-servers-evaluation.md`](../../technology/mcp-servers-evaluation.md) §3, §5).
- Shift handoff with organised material is a desk practice (`responsibilities.csv` R-15).

## Options considered

Continuous dashboard, prioritised queue, archive search, event timelines, topic dashboards, source comparison, maps,
briefings, email, messengers, webhooks, RSS out, REST, MCP, exports (brief Workstream I).

### Conflict: `datasette-mcp` (R4) vs a custom narrow MCP server (R7)

`datasette-mcp` exposes `execute_sql` over the whole database. That bypasses the licence `DisplayPolicy` (DR-3: full text
of licensed or non-redistributable items would be readable), returns untrusted text without trust labels, and exposes
every row ([`technology/mcp-servers-evaluation.md`](../../technology/mcp-servers-evaluation.md) §4 point 4; [`technology/mcp-tool-design.md`](../../technology/mcp-tool-design.md) §1 "never as the public surface"). **R7's design wins** for
the user-facing MCP surface. Datasette may be used by an operator locally for debugging against a read-only copy; it is not
part of the product.

## Decision

| Surface | MVP? | Notes |
|---|---|---|
| **Editorial queue** (web, Korean UI) | MUST | Events ranked by rules + bands; verdicts: report_to_desk / verify / ignore / archived, with a note; editor merge/split of events |
| **Item and event detail** | MUST | Provenance on every item (source, link, times, licence display level, independent-source count) |
| **Search** | MUST | FTS5 bigram + filters; optional LLM query rewrite |
| **Flash notice** | MUST | In-app (queue badge + browser notification while the page is open) and email to allow-listed internal recipients; per-event de-duplication |
| **Feed-health panel + incident notice** | MUST | Covers "tell the wire or engineering when a feed breaks" for the feeds the system collects |
| **Digest / briefing** (scheduled editions + shift handoff) | MUST | Draft → human review/edit → approve → email; delivery log (sent/failed) |
| **Profile editor** | MUST | Monitoring profiles without code (YAML import/export + form) |
| **Read-only JSON API** | MUST (the UI uses it) | Token auth; same `DisplayPolicy` |
| **Read-only MCP server (stdio)** | SHOULD | R7's v1 tools, wrapping the same service layer; Python MCP SDK (FastMCP), version pinned at build (not verified in phase 1) |
| Webhooks, RSS output, messengers (via apprise), Markdown/JSON export of a digest | DEFER (webhook + export SHOULD later) | apprise 2.3.0 parsed Telegram/Slack/mail URLs (TESTED parse-only) |
| Maps, topic dashboards, source-comparison views | DEFER | no evidence they change a desk action |
| MCP write tools, remote MCP over HTTP with OAuth 2.1 | DEFER | [`technology/mcp-tool-design.md`](../../technology/mcp-tool-design.md) §4 |

Outbound rule (M8): automatic sending only to allow-listed internal recipients and only for unflagged items; anything
else is queued for one-click approval. Feed-incident notices to an outside party (a wire agency) are always drafted for
human approval.

## Consequences

- One web app (FastAPI + Jinja2 templates + htmx) serves the UI and the JSON API; the MCP server is a separate stdio
  process reading the same SQLite file read-only.
- Without AI the queue, alerts, digest template and search still work (ADR-006).

## Evidence

[`business/industry-and-business-process-report.md`](../../business/industry-and-business-process-report.md) F-A-02, F-A-05, §4 · [`business/desk-practices.md`](../../business/desk-practices.md) · [`business/commercial-product-landscape.md`](../../business/commercial-product-landscape.md)
§3–§4 · [`technology/ai-and-agent-integration-report.md`](../../technology/ai-and-agent-integration-report.md) §6 · [`technology/mcp-tool-design.md`](../../technology/mcp-tool-design.md) · [`technology/mcp-servers-evaluation.md`](../../technology/mcp-servers-evaluation.md)
· [`technology/open-source-components-evaluation.md`](../../technology/open-source-components-evaluation.md) F-C-07.

## Reversal triggers

- Desk interviews show monitors notify by messenger → add an apprise channel (config only).
- A customer NRCS accepts webhook or file export of registered items → add the export/webhook integration point (ADR-010).
- MCP usage in the pilot is zero → drop the MCP server from the next release.
