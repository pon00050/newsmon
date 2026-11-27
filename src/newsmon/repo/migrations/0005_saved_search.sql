-- 0005_saved_search (duty 4, 중요영상 및 게시글 검색): searches a monitor keeps watching. Filters mirror the search page;
-- last_seen_utc drives the "new since last opened" count; alert = 1 raises a watch alert for new matches.
CREATE TABLE saved_search (search_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1, name TEXT NOT NULL,
  query TEXT NOT NULL, lang TEXT, source_key TEXT, band TEXT, hours INTEGER, video_only INTEGER NOT NULL DEFAULT 0,
  alert INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL, created_utc TEXT NOT NULL, last_seen_utc TEXT NOT NULL,
  last_error TEXT);
CREATE INDEX ix_saved_search_ws ON saved_search (workspace_id);
-- the 영상만 filter and the clip lookup on result rows read media_asset by article
CREATE INDEX ix_media_asset_article ON media_asset (article_id);
