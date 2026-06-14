"""Per-team news gathering from ESPN, BBC, and FIFA — via site-restricted
Google News RSS.

fifa.com (and ESPN's article pages) are JavaScript-rendered, so we can't scrape
their HTML with plain HTTP. Google News RSS exposes each outlet's coverage as
clean XML and supports `site:` filters, so we pull ESPN/BBC/FIFA headlines about
a specific team without a headless browser. The resulting text blob is handed to
the Scout's summariser model — replacing the paid web_search tool.
"""
from __future__ import annotations

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

from .base import fetch

log = logging.getLogger("fifa.crawl.news_sources")

GNEWS = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="

# Source label -> Google News site filter.
SOURCES = {
    "ESPN": "site:espn.com",
    "BBC": "site:bbc.com OR site:bbc.co.uk",
    "FIFA": "site:fifa.com",
}

PER_SOURCE = 6  # headlines per source per team


def _clean_title(title: str, source: str) -> str:
    # Google News appends " - <Outlet>"; drop it.
    for suffix in (f" - {source}", " - ESPN", " - BBC", " - FIFA", " - BBC Sport"):
        if title.endswith(suffix):
            return title[: -len(suffix)].strip()
    return title.strip()


def _source_headlines(team_name: str, source: str, site_filter: str) -> list[str]:
    q = f'"{team_name}" World Cup 2026 {site_filter}'
    url = GNEWS + urllib.parse.quote(q)
    try:
        xml = fetch(url, ttl_hours=6.0)  # cached; stale-on-failure
        root = ET.fromstring(xml)
    except Exception as exc:  # noqa: BLE001
        log.debug("news fetch failed for %s/%s: %s", team_name, source, exc)
        return []
    out: list[str] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        pub = item.findtext("pubDate") or ""
        when = ""
        try:
            when = datetime.strptime(pub[:16], "%a, %d %b %Y").strftime("%d %b")
        except Exception:  # noqa: BLE001
            pass
        line = _clean_title(title, source)
        out.append(f"- {line}" + (f" ({when})" if when else ""))
        if len(out) >= PER_SOURCE:
            break
    return out


def team_news_blob(team_name: str) -> str:
    """Recent ESPN/BBC/FIFA headlines about the team, grouped by source."""
    sections: list[str] = []
    for source, site_filter in SOURCES.items():
        lines = _source_headlines(team_name, source, site_filter)
        if lines:
            sections.append(f"## {source}\n" + "\n".join(lines))
    blob = "\n\n".join(sections)
    log.debug("news blob for %s: %d chars", team_name, len(blob))
    return blob
