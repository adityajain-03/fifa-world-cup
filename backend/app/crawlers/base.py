"""Shared HTTP fetching with a polite on-disk cache.

Used by the crawlers so repeated refreshes within the TTL don't re-hammer
the source sites, and so a transient network failure can fall back to the
last cached copy.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from ..config import settings

log = logging.getLogger("fifa.crawl")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "fifa-wc-2026-dashboard/0.1 (educational project)"
)


def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return settings.html_cache_dir / f"{h}.cache"


def fetch(url: str, *, ttl_hours: Optional[float] = None, params: dict | None = None) -> str:
    """GET a URL as text, using the on-disk cache when fresh.

    Falls back to a stale cached copy if the network request fails.
    """
    ttl = settings.html_cache_ttl_hours if ttl_hours is None else ttl_hours
    full = url
    if params:
        full = str(httpx.URL(url, params=params))
    path = _cache_path(full)
    settings.html_cache_dir.mkdir(parents=True, exist_ok=True)

    if path.exists() and (time.time() - path.stat().st_mtime) < ttl * 3600:
        return path.read_text(encoding="utf-8")

    try:
        resp = httpx.get(
            url, params=params, headers={"User-Agent": USER_AGENT},
            timeout=20.0, follow_redirects=True,
        )
        resp.raise_for_status()
        path.write_text(resp.text, encoding="utf-8")
        return resp.text
    except Exception as exc:  # noqa: BLE001
        if path.exists():
            log.warning("fetch failed for %s (%s); using stale cache", url, exc)
            return path.read_text(encoding="utf-8")
        log.warning("fetch failed for %s (%s); no cache available", url, exc)
        raise


def fetch_json(url: str, *, ttl_hours: Optional[float] = None, params: dict | None = None) -> Any:
    import json

    return json.loads(fetch(url, ttl_hours=ttl_hours, params=params))
