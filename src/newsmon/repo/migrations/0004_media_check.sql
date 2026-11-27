-- 0004_media_check (duty 2, footage check and ingest tracking): one row per wire clip, keyed by its media_asset and the
-- file hash it was checked at. Technical facts and fault times only; no media is copied. A thumbnail path is set only
-- where the source licence stores content in full.
CREATE TABLE media_check (asset_id INTEGER PRIMARY KEY REFERENCES media_asset, sha256 TEXT NOT NULL,
  checked_utc TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ok','needs_check','unreadable','missing')),
  probe_json TEXT, faults_json TEXT, notes_json TEXT, thumb_path TEXT, error TEXT,
  ingest_state TEXT NOT NULL DEFAULT 'pending' CHECK (ingest_state IN ('pending','filed')),
  ingest_by TEXT, ingest_utc TEXT);
