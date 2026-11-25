# MCP tool design: news-monitoring system (R7, 2026-11-25)

> **Status: Design proposal (not built).** Design for a read-only MCP surface. Not built in Release A + A.1.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

Purpose: let an external AI agent (Claude Desktop, Claude Code, or any MCP client) **query** the monitoring system's
archive, events, alerts and briefings. The system's own pipeline does **not** use MCP or agents internally (see 06 report
§4). This is a delivery surface for D8, comparable to the REST API, which it should wrap.

## 1. Protocol facts this design relies on

| Fact | Tag | Source (checked 2026-11-25) |
|---|---|---|
| A tool has `name`, `title`, `description`, `inputSchema`, an optional `outputSchema` and optional `annotations`. Results may carry `structuredContent`, which must conform to `outputSchema` if one is declared, plus a serialized TextContent copy for backward compatibility. | VERIFIED | https://modelcontextprotocol.io/specification/2025-06-18/server/tools |
| Clients **MUST** treat tool annotations as untrusted unless the server is trusted. | VERIFIED | same |
| Servers **MUST** validate all inputs, implement access controls, rate-limit invocations and sanitize outputs. Clients SHOULD keep a human in the loop for sensitive operations. | VERIFIED | same, §Security Considerations |
| Authorization is optional. For HTTP transports it is OAuth 2.1 with Protected Resource Metadata (RFC 9728). **stdio servers should take credentials from the environment instead.** | DOCUMENTED (search snippet of the spec page) | https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization |
| A newer revision exists (the "latest" page points to 2026-07-28; the draft removes protocol-level sessions from Streamable HTTP). | DOCUMENTED | https://modelcontextprotocol.io/specification/draft/changelog |
| The annotation hints are `readOnlyHint`, `destructiveHint`, `idempotentHint` and `openWorldHint`. | DOCUMENTED (MCP schema; not re-read in this round) | https://modelcontextprotocol.io/specification/2025-06-18/schema |

Implementation note: use the official Python MCP SDK (FastMCP) and pin a spec revision at build time. R4 owns the registry
of existing MCP servers. Prefer reusing a generic SQLite/Postgres MCP server only for operator debugging, never as the
public surface, because it exposes raw SQL.

## 2. Principles

1. **Read-only by default.** Version 1 exposes only query tools. Write tools (acknowledge an alert, add a watch term) are
   a separate, opt-in tool group behind a different token scope. Every write is reversible and logged. Nothing in MCP can
   send outside the system (no e-mail, no wire notification).
2. **Returned article text is untrusted.** Every tool that returns source text wraps it in a field named
   `untrusted_source_text` and sets a top-level `content_trust: "untrusted_third_party"`. The tool `description` tells the
   client model that this text is data. The server cannot make the client obey (threat T6), but it can make the boundary
   visible.
3. **AI output is labelled.** Fields the system generated with an LLM sit under `ai` with `model`, `prompt_version` and
   `generated_at`, kept separate from source fields. `injection_suspected` items are returned with `flags:
   ["injection_suspected"]`.
4. **Bounded responses.** Every list tool has `limit` (default 10, max 50) and a cursor. Body text is truncated
   (`max_chars`, default 2,000, max 8,000) unless `get_article` is called for a single item.
5. **Licence-aware.** Items carry `rights` from the source registry (R5/R9). Tools return only an excerpt for sources whose
   licence forbids redistribution (for example wire content on a contract that does not allow it).
6. **Auth.** For local use, the stdio transport with a token taken from the environment. For remote use, Streamable HTTP
   with OAuth 2.1 per the spec, scopes `news.read` and `news.write`, a per-token rate limit (e.g. 60 calls/min), and an
   audit log of every call (token, tool, arguments hash, result IDs).

## 3. Tools, version 1 (read-only)

Schemas are abbreviated JSON Schema. Each also declares an `outputSchema` matching the "returns" shape.

### 3.1 `search_articles`
Full-text and filter search over the archive (FTS5/BM25 underneath, per R6 and D4).
```json
{"type":"object","additionalProperties":false,"required":["query"],
 "properties":{
  "query":{"type":"string","description":"Keywords; Korean, English or Chinese. Supports quoted phrases."},
  "languages":{"type":"array","items":{"enum":["ko","en","zh","ja","other"]}},
  "sources":{"type":"array","items":{"type":"string"},"description":"Source IDs from list_sources"},
  "topics":{"type":"array","items":{"enum":["us_politics","north_korea","china","japan","disaster","conflict","korea_related","other"]}},
  "since":{"type":"string","format":"date-time"},"until":{"type":"string","format":"date-time"},
  "min_relevance":{"type":"integer","description":"0-100 desk relevance; validated server-side"},
  "limit":{"type":"integer","default":10},"cursor":{"type":"string"}}}
```
Returns `{items:[{article_id, title, source_id, url, published_at, language, event_id, relevance_band, flags,
ai:{headline_ko, summary_ko}, snippet}], next_cursor, content_trust}`.
Annotations: `readOnlyHint: true`, `openWorldHint: false`.

### 3.2 `get_article`
`{article_id: string, include_text: boolean = false, max_chars: integer = 2000}`. Returns the metadata, the `ai`
extraction (who, what, where, when, claims with attribution), the `untrusted_source_text` if requested and allowed by the
licence, `text_sha256`, and the `duplicates` (article IDs in the same dedup cluster).

### 3.3 `get_event`
`{event_id: string}`. Returns the event cluster (R6): canonical title, first-seen and last-updated times, member articles
with source and language, a timeline of developments, and `conflicts`, the claims on which sources disagree (deterministic
table built from extracted claims; only the side-by-side wording comes from an LLM).

### 3.4 `list_events`
`{since?, topics?, min_sources?: integer, sort: "recent"|"size"|"relevance", limit, cursor}`. This is "what is
developing now".

### 3.5 `list_alerts`
`{since?: date-time, status?: "new"|"acknowledged"|"dismissed", severity?: "flash"|"high"|"normal", limit, cursor}`.
Returns the alerts the rules engine raised (keyword or watchlist hits, relevance-band thresholds, feed-health incidents),
each with its `reason` (the rule ID and matched terms) and its linked `article_id` or `event_id`.

### 3.6 `get_briefing`
`{briefing_id?: string, date?: date, edition?: "morning"|"evening"|"adhoc"}`. Returns a stored briefing: sections, each
bullet with `cited_article_ids` (the server checks they exist), the model and prompt version, and its human-review status.
It **returns a stored artefact**; it does not generate one on demand. On-demand generation would be a costed,
rate-limited write-type operation.

### 3.7 `get_feed_status`
`{source_id?: string}`. Returns the last successful fetch, the error streak, the items per hour against baseline, and an
`incident` flag. This supports the desk's "tell the wire service or engineering when a feed breaks" duty.

### 3.8 `list_sources`
No arguments. Returns source IDs, names, languages, collection method and the `rights` summary.

## 4. Tools, version 2 (opt-in, `news.write` scope)

| Tool | Effect | Guard |
|---|---|---|
| `acknowledge_alert {alert_id, note?}` | Sets the alert status | Idempotent, reversible, logged |
| `add_watch_term {term, languages, severity}` | Adds a keyword rule | Max N per token, logged, reversible |
| `request_briefing {scope, since}` | Queues a briefing job (costed LLM call) | Daily quota; output lands in the review queue, not sent anywhere |

Explicitly **not** exposed: anything that sends messages outside the system, edits source text, deletes records, runs
SQL, or fetches arbitrary URLs. A URL-fetch tool would turn the server into an exfiltration and SSRF vector (threat
model T4).

## 5. Prompts and resources (optional)

- MCP **prompts**: `desk_briefing_template` and `compare_reports_template`, so a Claude Desktop user gets a consistent
  briefing flow that runs on the client's own model.
- MCP **resources**: `news://briefing/{date}/{edition}` and `news://event/{id}`, for clients that prefer attaching context
  to calling tools.

## 6. When an agent is justified

Using the MCP server from Claude Desktop or Code **is** the agent use case, and it runs on the user's side. Inside the
system, a runtime agent is justified only for **research assistance**: open-ended questions such as "trace how coverage of
X evolved across sources this month". The path is unknown in advance there, a human reads the result, and errors are
recoverable. Even then, it should be a single agent with these read-only tools, a step budget and no outbound tools. It is
a round-2 or round-3 feature, not MVP. No multi-agent runtime.
