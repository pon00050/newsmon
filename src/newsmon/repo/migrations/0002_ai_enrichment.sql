-- 0002_ai_enrichment (Release A.1): injection pre-filter flag on articles (FR-14 runs in every mode) and a small
-- key/value table for operator switches that must survive a restart (the AI on/off toggle).
ALTER TABLE article ADD COLUMN regex_prefilter_hit INTEGER NOT NULL DEFAULT 0;
CREATE TABLE app_state (workspace_id INTEGER NOT NULL DEFAULT 1, key TEXT NOT NULL, value TEXT NOT NULL,
  updated_utc TEXT NOT NULL, PRIMARY KEY (workspace_id, key));
CREATE INDEX ix_ai_target ON ai_interpretation (target_kind, target_id, task);
