"""Repository base: every repository is bound to one workspace and passes `workspace_id` in every statement on an
owned table (ADR-009 #4, NFR-23). All SQL lives under repo/ (NFR-22)."""
from __future__ import annotations

from newsmon.repo.db import Database

# Root tables that carry workspace_id NOT NULL. Child tables reach a root through a foreign key (amendment 2).
ROOT_TABLES = ("source", "feed", "fetch_run", "quarantine", "article", "feed_entry", "event", "ai_interpretation",
               "entity", "editorial_assessment", "profile", "alert", "incident", "digest", "outbox", "app_user",
               "audit_log", "spend_day", "app_state")
CHILD_TABLES = {"inbox_ledger": "feed", "article_revision": "article", "near_dup_link": "article_revision",
                "media_asset": "article", "event_member": "event", "article_embedding": "article",
                "claim": "article_revision", "entity_mention": "article_revision", "rule_hit": "article",
                "source_health": "feed", "digest_item": "digest", "delivery_log": "outbox", "api_token": "app_user"}


class BaseRepo:
    def __init__(self, db: Database, workspace_id: int = 1) -> None:
        self.db = db
        self.workspace_id = workspace_id
