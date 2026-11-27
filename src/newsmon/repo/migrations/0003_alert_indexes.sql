-- 0003_alert_indexes (M1 v1 review): the alert badge and poll read the count of new alerts on every page and every 20 s;
-- the uniqueness rules (one alert per kind and article, one open incident per feed) are enforced by the database as
-- well as by the code, so a CLI collect running beside the web collector cannot duplicate them.
CREATE INDEX ix_alert_ws_status ON alert (workspace_id, status);
CREATE UNIQUE INDEX ux_alert_kind_article ON alert (kind, article_id) WHERE article_id IS NOT NULL;
CREATE UNIQUE INDEX ux_incident_open ON incident (feed_id) WHERE closed_utc IS NULL;
