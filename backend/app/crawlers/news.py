"""World Cup news headlines from ESPN's public news endpoint."""
from __future__ import annotations

import logging

from .base import fetch_json

log = logging.getLogger("fifa.crawl.news")

NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/news"


def crawl_news(limit: int = 12) -> list[dict]:
    try:
        data = fetch_json(NEWS_URL, ttl_hours=1.0)
    except Exception:  # noqa: BLE001
        log.warning("ESPN news unreachable")
        return []
    out = []
    for a in (data.get("articles") or [])[:limit]:
        links = a.get("links") or {}
        web = (links.get("web") or {}).get("href") or (links.get("mobile") or {}).get("href")
        images = a.get("images") or []
        out.append({
            "headline": a.get("headline") or a.get("title") or "",
            "description": a.get("description") or "",
            "published": a.get("published") or "",
            "link": web or "",
            "image": images[0].get("url") if images else None,
        })
    log.info("ESPN news: %d headlines", len(out))
    return out
