# MCP servers for news and monitoring data (R4, 2026-11-25)

> **Status: Verified finding.** Ratings are a reading of repository metadata, not usage tests.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Informs:** D8 (is MCP a delivery surface?), and R7's tool design. All dates 2026-11-25.
**Raw data:** private experiment data (not published) (query script `mcp_registry_query.py`).

## 1. How the survey was done

- Official reference repo `modelcontextprotocol/servers` read via `gh api` (README, `src/` listing, fetch server pyproject/README).
- Official registry `https://registry.modelcontextprotocol.io/v0.1/servers?search=<q>&version=latest&limit=100`, queries:
  rss, feed, atom, gdelt, news, headline, sqlite, datasette, fetch, scrape, crawl, monitor, media.
  **Controls:** the nonsense query `zzqxjvkw` returned 0 entries; the known-answer query `fetch` returned results. So a
  0 result (here: `datasette` = 0 registry entries) is a real absence from the registry, though the server exists on
  GitHub (found by `gh search repos`). Substring search is broad ("feed", "atom", "news" hit the 100-row cap with noise), so
  relevant rows were picked by reading names and descriptions, not counted.
- Maintenance for chosen servers via `gh api repos/...`.
- Not done: installing or running any third-party MCP server (no round-1 decision needs it), and no test of any hosted server
  (sending our queries to a third party was not warranted).

## 2. What the official repo contains (VERIFIED, `gh api` + README)

Current reference servers: `everything, fetch, filesystem, git, memory, sequentialthinking, time`. **There is no SQLite, RSS or
news server in the official repo.** The old SQLite, Postgres, Slack, Puppeteer and Brave servers were moved to
`modelcontextprotocol/servers-archived` (archived=true, last push 2025-05-28). The README says the reference servers are
"educational examples... not production-ready solutions". Licence file reads "Other" (GitHub NOASSERTION); the fetch server
declares MIT.

## 3. Candidates by need

Ratings are my reading of the metadata, not usage tests: maturity = repo age/activity/stars/licence; security = what a
user must trust. All rows verified 2026-11-25 against the registry JSON or `gh api`; tag VERIFIED for metadata, nothing here
is TESTED.

| Need | Server | Transport | Maturity (metadata) | Security notes | Verdict |
|---|---|---|---|---|---|
| Query our own SQLite | **`datasette/datasette-mcp`** (Datasette org plugin; `/-/mcp`) | Streamable HTTP | Apache-2.0, 21 stars, pushed 2026-10-22; official org | Read-only tools by default (`list_databases`, `get_database_schema`, `execute_sql`); enforces Datasette permissions per call; writable canned queries are opt-in and annotated destructive; `register_mcp_tools` hook adds custom tools | **Best first MCP surface** (INFERRED: Datasette also TESTED serving our SQLite) |
| Query our own SQLite | `arifulislamat/database-mcp` (`database-mcp-sqlite`) | stdio | MIT, 5 stars, pushed 2026-11-22 | Description: read-only by default, row caps, statement timeouts (DOCUMENTED, not read in code) | Runner-up |
| Query our own SQLite | `xakpc/sqlite-mcp-sidecar` | HTTP | Apache-2.0, 1 star | "read-only default, bounded writes" (DOCUMENTED) | Watch |
| Global news (external) | **`cyanheads/gdelt-mcp-server`** | stdio + HTTP | Apache-2.0, 10 stars, pushed 2026-11-25, 11 tools | Uses GDELT public APIs, no key. Tools: article search, sentence search, coverage timeline, tone, coverage by language/country, themes, TV captions/clips/stations. Third-party code | Good candidate for an "outside-world context" tool; GDELT data licence is R9's question |
| Global news (external) | 5 other GDELT servers in the registry (`benbarazandeh/gdelt-news-monitor`, `pipeworx-io/gdelt`, `mrfentmen/gdelt-mcp`, ...) | mixed | single-author, young | Several are hosted remotes that send queries to the operator | Ignore; one is enough |
| Feeds | `ni-c/freshrss-mcp` | stdio | MIT, 5 stars, pushed 2026-11-23 | Needs a FreshRSS instance and credentials | Only if FreshRSS is adopted (R3 scope) |
| Feeds | `kwp-lab/rss-reader-mcp` | hosted via Smithery | MIT, last push 2025-09-10 | Requires a Smithery bearer token; third-party hosting | Reject (stale, hosted) |
| Feeds | `ux-xd/rss-feed-mcp`, `Nero-Engine/rss-feed-reader`, `kriton-dev/rss-feed-reader`, `bepolabs/rss-reader`, `checkrss.com/mcp` and ~15 more | mostly hosted remote | 0-5 stars, 2026 vintage | Fetching happens on someone else's server, usually with no source code; some have x402 payment terms | Reject for production: our feeds must be fetched from our machine with our UA and polite intervals |
| Registry entry without a repo | `mrfentmen/rss-mcp` points at `github.com/mrfentmen/rss-mcp`, which returns **404** | stdio | n/a | Dangling listing | Reject; shows registry entries are self-published and unvetted |
| Fetch a URL | `modelcontextprotocol/servers/src/fetch` (`mcp-server-fetch` 2026.11.18, MIT) | stdio | Official reference server, Beta | README: obeys robots.txt (protego), refuses private/loopback/metadata IPs and re-checks redirects by default; `--allow-private-ips` removes that | Acceptable for ad-hoc agent reading; not our ingestion path |
| Web search | `brave/brave-search-mcp-server` (replaces archived official one) | stdio | MIT, 1592 stars, pushed 2026-11-24 | Needs a Brave API key (none held: BLOCKED-no-key) | Not tested |
| Hosted "news" servers (Google News wrapper, Newzai, Typesearch, newsmind ...) | various | hosted remote | young, mostly closed source | Query leaves our boundary; several need keys or payments | Reject for the core; they are comparators for R2 |

## 4. Security assessment (applies to the whole category)

1. **Registry listings are self-published.** There is no vetting signal beyond a status flag; one entry (`mrfentmen/rss-mcp`) has
   no repository at all, one (`browserssh`) was deprecated for describing a product that no longer exists.
2. **Hosted remote servers move our traffic to a stranger.** Anything we query (watch terms, source lists) is visible to the operator,
   and fetches carry their IP and UA, not ours. For a system whose method depends on a polite descriptive UA, that is disqualifying
   for ingestion.
3. **Prompt injection through news content.** Any tool that returns article text hands attacker-controlled text to the model. The
   fetch server's own README warns about this class of risk. Our own MCP tools must return fields marked as untrusted data and must
   never put article text into tool descriptions or error strings. R7 owns the test.
4. **Read-only by default, writes separate.** datasette-mcp's default (three read-only tools, destructive tools opt-in) is the right
   pattern to copy. Raw `execute_sql` is the main risk of any SQLite MCP: it exposes the schema and every row. Datasette's
   permission model and read-only connection limit it, but a custom, narrow tool set is safer for the archive and any private notes.
5. **SSRF in any fetch-type tool.** The official fetch server blocks private ranges by default; any custom `fetch_and_extract` tool
   needs the same guard plus a robots check and a per-host allowlist.

## 5. Custom MCP tools this system should expose (input to R7)

Design goal: the model queries our curated store and does not browse. Names are proposals.

| Tool | Inputs | Returns | Mode | Why it exists (seat duty) |
|---|---|---|---|---|
| `search_items` | query, since/until, source[], lang, limit | items: id, title, source, published_at, url, lang, snippet, event_id | read | "중요 영상·게시글 검색", find coverage fast |
| `get_item` | id | full extracted text, metadata, extraction method, dedup cluster | read | read the story |
| `list_events` | since, min_sources, topic filter | clusters with headline, first-seen time, source count, languages | read | what is breaking, wire vs follow-ups |
| `get_event` | event_id | member items in time order, first source, divergence between sources | read | the desk summary |
| `list_sources` / `get_source_health` | source id | last success, last item, HTTP status, items/hour, silence alarm | read | "외신사·기술국 통보": detect a feed that stopped |
| `get_digest` | window (e.g. morning/evening), watchlist | ranked items per watch topic | read | clipping firms' morning/evening reports |
| `list_watchlists` / `get_watch_hits` | watchlist id, since | matched items and which term matched | read | client monitoring |
| `lookup_archive` | document type (e.g. briefing transcript), date range, query | archived documents with citation | read | "아카이브 저장·정리 (국무부 브리핑 녹취)" |
| `fetch_and_extract` | url | extracted text and metadata, only for allowlisted hosts after robots check | read, rate-limited | one-off retrieval without opening the whole web |
| `flag_item` / `set_watchlist` | id, label / terms | confirmation | **write, destructive-annotated** | reporting to the desk; kept in a separate scope from the read tools |
| `translate_summarize` (optional, R7) | item id, target language, length | machine summary with model name and a source link | read; calls a cloud LLM | "영문 텍스트 요약" for reporters; must show it is machine output |

Build path (INFERRED): start with datasette-mcp over the SQLite file plus canned queries for `search_items`, `list_events` and
`get_source_health`; add the write and fetch tools only in a custom server once the read path is proven. The
`register_mcp_tools(datasette, mcp)` hook in datasette-mcp (README) lets custom Python tools live in the same process.

## 6. What this means for D8

MCP is cheap to add on top of a SQLite store (INFERRED from datasette-mcp), so it need not be decided now: keep the store and the
canned queries clean and MCP follows. It does not replace a queue UI or digest for a human desk (R1/R7 decide that). No existing
server supplies feeds or news ingestion in a form this project can trust.
