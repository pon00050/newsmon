"""Registrable domain (eTLD+1) from the bundled public-suffix snapshot: no network, no cache writes (FR-09)."""
from __future__ import annotations

from functools import lru_cache

import tldextract

_EXTRACT = tldextract.TLDExtract(cache_dir=None, suffix_list_urls=())


@lru_cache(maxsize=8192)
def registrable_domain(url: str | None) -> str | None:
    if not url:
        return None
    r = _EXTRACT(url)
    return r.top_domain_under_public_suffix or None
