-- 0006_event_member_article (event tracking): additive index only. event_member's primary key is (event_id, article_id),
-- so "which event is this article in" and the events stage's "articles in no event yet" anti-join would otherwise scan
-- the whole membership table once per article.
CREATE INDEX ix_event_member_article ON event_member (article_id);
