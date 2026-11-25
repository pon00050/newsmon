-- 0001_initial: schema of 05_architecture/11 section 5 plus its amendments box (feed_entry; workspace_id on spend_day;
-- audit_log op_kind/derivative_kind/retention_until/credential_ref). Portable types only (ADR-004): INTEGER, REAL, TEXT,
-- BLOB. Timestamps are ISO-8601 UTC text. Columns added beyond 11 section 5 are marked "T-07".

CREATE TABLE workspace (workspace_id INTEGER PRIMARY KEY, name TEXT NOT NULL, use_context TEXT NOT NULL
  CHECK (use_context IN ('private','internal')), created_utc TEXT NOT NULL);

CREATE TABLE source (
  source_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1 REFERENCES workspace,
  key TEXT NOT NULL, name TEXT NOT NULL, registrable_domain TEXT, owner_group TEXT, lang_default TEXT, country TEXT,
  is_wire INTEGER NOT NULL DEFAULT 0,
  access_method TEXT NOT NULL CHECK (access_method IN ('feed','http_api','directory','wire_api','nrcs_inbound','changedetection','rsshub')),
  tos_url TEXT, tos_checked_on TEXT, robots_ok INTEGER,
  storage TEXT NOT NULL DEFAULT 'metadata' CHECK (storage IN ('none','metadata','transient','full')),
  display TEXT NOT NULL DEFAULT 'headline' CHECK (display IN ('none','headline','snippet','full')),
  ai_processing TEXT NOT NULL DEFAULT 'unknown' CHECK (ai_processing IN ('yes','no','unknown')),
  external_ai_allowed INTEGER NOT NULL DEFAULT 0,
  redistribution TEXT NOT NULL DEFAULT 'none' CHECK (redistribution IN ('none','internal','external')),
  training TEXT NOT NULL DEFAULT 'no' CHECK (training = 'no'),
  licence_owner TEXT NOT NULL DEFAULT 'unknown' CHECK (licence_owner IN ('provider','tenant','public-domain','unknown')),
  allowed_contexts TEXT NOT NULL DEFAULT 'private,internal',
  retention_days INTEGER, attribution_text TEXT,
  permitted_ops TEXT NOT NULL DEFAULT '[]',
  third_party_processors_allowed INTEGER NOT NULL DEFAULT 0, authorised_users TEXT, territory TEXT,
  licence_holder TEXT, agreement_ref TEXT, valid_until TEXT, attested_by TEXT, attested_on TEXT,
  checklist_json TEXT,
  synthetic INTEGER NOT NULL DEFAULT 0,
  boilerplate_rules TEXT, live_patterns TEXT, story_key_rule TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  inactive_reason TEXT,                                                         -- T-07: why a row is inactive
  created_utc TEXT NOT NULL,
  UNIQUE (workspace_id, key),
  CHECK (licence_owner <> 'tenant' OR retention_days IS NOT NULL),
  CHECK (licence_owner <> 'tenant' OR active = 0 OR attested_on IS NOT NULL)
);

CREATE TABLE feed (
  feed_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, source_id INTEGER NOT NULL REFERENCES source,
  kind TEXT NOT NULL CHECK (kind IN ('rss','atom','api','gdelt','directory','wire_api','nrcs')),
  url_or_path TEXT NOT NULL, discovered_from TEXT NOT NULL, poll_seconds INTEGER NOT NULL DEFAULT 600,
  etag TEXT, last_modified TEXT, cursor TEXT, secret_name TEXT,
  next_due_utc TEXT,                                                            -- T-07: scheduling state
  active INTEGER NOT NULL DEFAULT 1, UNIQUE (workspace_id, url_or_path)
);

CREATE TABLE fetch_run (
  run_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, feed_id INTEGER NOT NULL REFERENCES feed,
  started_utc TEXT NOT NULL, finished_utc TEXT, status TEXT NOT NULL CHECK (status IN ('ok','not_modified','empty','error')),
  http_status INTEGER, bytes INTEGER, entries INTEGER, new_articles INTEGER,
  error_class TEXT CHECK (error_class IN ('timeout','http_4xx','http_5xx','parse','rate_limited','robots','ssrf_blocked','io','quarantine')),
  error_detail TEXT, attempt INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE inbox_ledger (
  feed_id INTEGER NOT NULL REFERENCES feed, rel_path TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
  sha256 TEXT NOT NULL, detected_format TEXT,
  status TEXT NOT NULL CHECK (status IN ('ingested','quarantined','media','gone')),   -- T-07: 'gone' (FR-28(f))
  reason TEXT, seen_utc TEXT NOT NULL, PRIMARY KEY (feed_id, rel_path, sha256)
);

CREATE TABLE quarantine (q_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, run_id INTEGER REFERENCES fetch_run,
  raw_ref TEXT, reason TEXT NOT NULL, created_utc TEXT NOT NULL);

CREATE TABLE article (
  article_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, uid TEXT NOT NULL UNIQUE,
  source_id INTEGER NOT NULL REFERENCES source, source_uri TEXT,
  canonical_url TEXT, item_type TEXT NOT NULL DEFAULT 'text' CHECK (item_type IN ('text','video','audio','picture')),
  lang TEXT, slugline TEXT, located TEXT, urgency INTEGER, pubstatus TEXT DEFAULT 'usable', embargoed_utc TEXT,
  usageterms TEXT, restrictions TEXT,
  subjects TEXT, attributes TEXT,
  first_seen_utc TEXT NOT NULL, published_utc TEXT, published_raw TEXT,
  current_revision_id INTEGER REFERENCES article_revision,
  status TEXT NOT NULL DEFAULT 'live' CHECK (status IN ('live','corrected','withdrawn','gone','killed')),
  story_key TEXT, is_live INTEGER NOT NULL DEFAULT 0,
  rule_band TEXT CHECK (rule_band IN ('drop','review','report','flash')), final_band TEXT,
  rule_score REAL,                                                              -- T-07: ranking score (FR-17)
  enrichment_status TEXT NOT NULL DEFAULT 'pending' CHECK (enrichment_status IN ('pending','done','failed','review','not_allowed')),
  licence_snapshot TEXT NOT NULL,
  synthetic INTEGER NOT NULL DEFAULT 0,                                         -- T-07: provenance only (FR-27(d))
  dup_of INTEGER REFERENCES article,                                            -- T-07: queue collapses near/exact dups onto the earliest
  reg_domain TEXT,                                                              -- T-07: registrable domain (FR-09)
  UNIQUE (workspace_id, source_id, source_uri), UNIQUE (workspace_id, source_id, canonical_url)
);

CREATE TABLE article_revision (
  revision_id INTEGER PRIMARY KEY, article_id INTEGER NOT NULL REFERENCES article, fetched_utc TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,                                           -- T-07: wire version
  headline TEXT, description_text TEXT, body_text TEXT,
  body_extractor TEXT, parser TEXT NOT NULL, raw_ref TEXT, raw_sha256 TEXT,
  content_sha256 TEXT NOT NULL, minhash BLOB,
  change_kind TEXT CHECK (change_kind IN ('initial','update','correction','withdrawal','kill')),
  renditions TEXT, associations TEXT,                                           -- T-07: ninjs JSON
  UNIQUE (article_id, content_sha256)
);

CREATE TABLE feed_entry (                                                       -- amendment 1
  workspace_id INTEGER NOT NULL DEFAULT 1, source_id INTEGER NOT NULL REFERENCES source,
  feed_id INTEGER REFERENCES feed, article_id INTEGER NOT NULL REFERENCES article,
  feed_guid TEXT NOT NULL, seen_utc TEXT NOT NULL,
  UNIQUE (source_id, feed_guid)
);

CREATE TABLE near_dup_link (a_revision_id INTEGER NOT NULL REFERENCES article_revision, b_revision_id INTEGER NOT NULL REFERENCES article_revision,
  jaccard_est REAL NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('same_item','syndicated','revision')), method TEXT NOT NULL,
  PRIMARY KEY (a_revision_id, b_revision_id));

CREATE TABLE media_asset (asset_id INTEGER PRIMARY KEY, article_id INTEGER REFERENCES article,
  kind TEXT CHECK (kind IN ('image','video','audio','transcript')), href TEXT, sha256 TEXT, size_bytes INTEGER,
  content_type TEXT, duration_s REAL, width INTEGER, height INTEGER, rights_note TEXT, recorded_utc TEXT NOT NULL);

CREATE TABLE event (event_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, uid TEXT NOT NULL UNIQUE,
  first_seen_utc TEXT NOT NULL, last_update_utc TEXT NOT NULL, centroid BLOB, centroid_model TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','dormant','closed','merged')), merged_into INTEGER REFERENCES event,
  independent_sources INTEGER NOT NULL DEFAULT 0, final_band TEXT, algo TEXT NOT NULL);
CREATE TABLE event_member (event_id INTEGER NOT NULL REFERENCES event, article_id INTEGER NOT NULL REFERENCES article,
  similarity REAL, added_utc TEXT NOT NULL, added_by TEXT NOT NULL, PRIMARY KEY (event_id, article_id));
CREATE TABLE article_embedding (article_id INTEGER PRIMARY KEY REFERENCES article, model TEXT NOT NULL, vector BLOB NOT NULL, created_utc TEXT NOT NULL);

CREATE TABLE ai_interpretation (
  interp_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1,
  target_kind TEXT NOT NULL CHECK (target_kind IN ('revision','event','digest')), target_id INTEGER NOT NULL,
  task TEXT NOT NULL CHECK (task IN ('triage','enrich','digest_draft','query_rewrite')),
  output_json TEXT NOT NULL, generated_by_ai INTEGER NOT NULL DEFAULT 1 CHECK (generated_by_ai = 1),
  provider TEXT NOT NULL, endpoint_kind TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL, schema_version TEXT NOT NULL,
  input_sha256 TEXT NOT NULL, fields_sent TEXT NOT NULL,
  validation_status TEXT NOT NULL CHECK (validation_status IN ('valid','invalid','retried_valid','review')),
  injection_suspected INTEGER NOT NULL DEFAULT 0, regex_prefilter_hit INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, latency_ms INTEGER, created_utc TEXT NOT NULL,
  UNIQUE (target_kind, target_id, task, model, prompt_version, schema_version, input_sha256)
);
CREATE TABLE claim (claim_id INTEGER PRIMARY KEY, revision_id INTEGER NOT NULL REFERENCES article_revision, text TEXT NOT NULL,
  attributed_to TEXT, attribution_type TEXT, extracted_by INTEGER REFERENCES ai_interpretation);
CREATE TABLE entity (entity_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, kind TEXT, canonical_name TEXT,
  wikidata_qid TEXT, names_json TEXT);
CREATE TABLE entity_mention (revision_id INTEGER REFERENCES article_revision, entity_id INTEGER REFERENCES entity,
  surface TEXT, name_ko TEXT, method TEXT);
CREATE TABLE editorial_assessment (assess_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1,
  target_kind TEXT NOT NULL CHECK (target_kind IN ('article','event')), target_id INTEGER NOT NULL, editor TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK (verdict IN ('report_to_desk','verify','ignore','archived')), note TEXT,
  based_on_interp_id INTEGER REFERENCES ai_interpretation, created_utc TEXT NOT NULL);

CREATE TABLE profile (profile_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, key TEXT NOT NULL,
  yaml TEXT NOT NULL, version INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, updated_by TEXT, updated_utc TEXT NOT NULL,
  UNIQUE (workspace_id, key, version));
CREATE TABLE rule_hit (article_id INTEGER NOT NULL REFERENCES article, profile_id INTEGER NOT NULL REFERENCES profile,
  rule_id TEXT NOT NULL, matched TEXT, score REAL, created_utc TEXT NOT NULL, PRIMARY KEY (article_id, profile_id, rule_id));
CREATE TABLE alert (alert_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, kind TEXT NOT NULL
  CHECK (kind IN ('flash','spike','watch','feed_incident')), severity TEXT NOT NULL, event_id INTEGER, article_id INTEGER,
  incident_id INTEGER, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','acknowledged','dismissed')),
  created_utc TEXT NOT NULL);
CREATE TABLE incident (incident_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, feed_id INTEGER NOT NULL REFERENCES feed,
  kind TEXT NOT NULL CHECK (kind IN ('failing','empty','silent')), opened_utc TEXT NOT NULL, closed_utc TEXT, detail TEXT);
CREATE TABLE source_health (feed_id INTEGER REFERENCES feed, day TEXT, fetches INTEGER, failures INTEGER, median_latency_ms INTEGER,
  items INTEGER, last_success_utc TEXT, PRIMARY KEY (feed_id, day));
CREATE TABLE digest (digest_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, profile_id INTEGER REFERENCES profile,
  edition TEXT NOT NULL CHECK (edition IN ('morning','evening','handoff','adhoc')), window_start_utc TEXT NOT NULL, window_end_utc TEXT NOT NULL,
  draft_kind TEXT NOT NULL CHECK (draft_kind IN ('ai','template')), body_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','in_review','approved','sent','failed')), reviewed_by TEXT, approved_utc TEXT);
CREATE TABLE digest_item (digest_id INTEGER NOT NULL REFERENCES digest, article_id INTEGER, event_id INTEGER, position INTEGER NOT NULL);
CREATE TABLE outbox (msg_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, channel TEXT NOT NULL, recipient TEXT NOT NULL,
  subject TEXT, body TEXT NOT NULL, needs_approval INTEGER NOT NULL, approved_by TEXT,
  status TEXT NOT NULL CHECK (status IN ('queued','awaiting_approval','sent','failed')), attempts INTEGER NOT NULL DEFAULT 0, created_utc TEXT NOT NULL);
CREATE TABLE delivery_log (msg_id INTEGER REFERENCES outbox, at_utc TEXT NOT NULL, result TEXT NOT NULL, detail TEXT);

CREATE TABLE app_user (user_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, login TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('viewer','editor','admin')), password_hash TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE api_token (token_id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES app_user, token_hash TEXT NOT NULL UNIQUE,
  scopes TEXT NOT NULL, created_utc TEXT NOT NULL, revoked_utc TEXT);
CREATE TABLE audit_log (audit_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, at_utc TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, target TEXT, licence_flags TEXT, detail TEXT,
  op_kind TEXT, derivative_kind TEXT, retention_until TEXT, credential_ref TEXT);         -- amendment 5
CREATE TABLE spend_day (workspace_id INTEGER NOT NULL DEFAULT 1, day TEXT NOT NULL, usd REAL NOT NULL DEFAULT 0,
  cap_usd REAL NOT NULL, capped INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (workspace_id, day));  -- amendment 2

CREATE VIRTUAL TABLE search_fts USING fts5(headline_tok, text_tok, ai_tok, entity_tok,
  content='', contentless_delete=1, tokenize='unicode61 remove_diacritics 2');

CREATE INDEX ix_article_ws_seen ON article (workspace_id, first_seen_utc);
CREATE INDEX ix_article_source_seen ON article (source_id, first_seen_utc);
CREATE INDEX ix_article_band ON article (final_band);
CREATE INDEX ix_article_story ON article (source_id, story_key);
CREATE INDEX ix_revision_hash ON article_revision (content_sha256);
CREATE INDEX ix_event_update ON event (last_update_utc);
CREATE INDEX ix_fetch_run_feed ON fetch_run (feed_id, started_utc);
CREATE INDEX ix_feed_entry_article ON feed_entry (article_id);
CREATE INDEX ix_article_dup ON article (dup_of);
