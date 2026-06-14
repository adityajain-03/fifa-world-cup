"""Squad rosters from the Wikipedia '2026 FIFA World Cup squads' article.

Best-effort: Wikipedia squad tables follow a fairly stable layout
(No. / Pos. / Player / DOB / Caps / Goals / Club). We associate each
`wikitable` with the most recent team heading in document order. Parsing
failures are tolerated — rosters enrich the UI and Scout context but are not
required for the bracket simulation.
"""
from __future__ import annotations

import logging
import re

from selectolax.parser import HTMLParser

from ..models import Player, Team
from .aliases import canonical, name_slug
from .base import fetch

log = logging.getLogger("fifa.crawl.wiki")

SQUADS_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
ARTICLE_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"

POS_RE = re.compile(r"\b(GK|DF|MF|FW|DEF|MID|FWD)\b", re.I)
# Country links use either "<X>_national_football_team" or, for some federations
# (USA/Canada), "<X>_men's_national_soccer_team".
NAT_RE = re.compile(r"national_(football|soccer)_team", re.I)


def crawl_groups() -> dict[str, list[str]]:
    """Official A-L groups from the article's per-group standings tables.

    Each group renders a 4-team standings table; they appear in group order, so
    we label them A..L by document order. Returns {} on any parse failure or if
    we don't recover exactly 12 groups (caller then falls back to ESPN).
    """
    import string

    try:
        html = fetch(ARTICLE_URL, ttl_hours=6.0)
    except Exception:  # noqa: BLE001
        log.warning("Wikipedia article unreachable")
        return {}

    tree = HTMLParser(html)
    groups: list[list[str]] = []
    for table in tree.css("table"):
        if "wikitable" not in (table.attributes.get("class") or ""):
            continue
        text = table.text()
        if "Pos" not in text and "Pld" not in text:  # standings table only
            continue
        names: list[str] = []
        for a in table.css("a[href]"):
            if NAT_RE.search(a.attributes.get("href") or ""):
                nm = a.text(strip=True)
                if nm and nm not in names:
                    names.append(nm)
        if len(names) == 4:
            groups.append(names)

    if len(groups) != 12:
        log.warning("Wikipedia groups: found %d (need 12); falling back", len(groups))
        return {}
    out = {string.ascii_uppercase[i]: g for i, g in enumerate(groups)}
    log.info("Wikipedia: recovered 12 official groups A-L")
    return out


def _int_or_none(text: str):
    text = text.strip().replace(",", "")
    return int(text) if text.isdigit() else None


def crawl_squads(teams: list[Team]) -> dict[str, list[Player]]:
    # Build a name -> slug map from the real teams in the field.
    alias = {canonical(t.name).lower(): t.id for t in teams}
    for t in teams:
        alias[t.name.lower()] = t.id
    known_names = set(alias.keys())
    try:
        html = fetch(SQUADS_URL, ttl_hours=24.0)
    except Exception:  # noqa: BLE001
        log.warning("Wikipedia squads page unreachable")
        return {}

    tree = HTMLParser(html)
    rosters: dict[str, list[Player]] = {}
    current_slug: str | None = None

    # Iterate headings and tables in document order.
    for node in tree.css("h2, h3, h4, table"):
        tag = node.tag
        if tag in ("h2", "h3", "h4"):
            heading = node.text(strip=True)
            heading = re.sub(r"\[edit\]$", "", heading).strip()
            low = heading.lower()
            if low in alias:
                current_slug = alias[low]
            elif low in known_names:
                current_slug = alias.get(low, name_slug(heading))
            else:
                # Heading may include extra text; try first matching known name.
                match = next((n for n in known_names if n and n in low), None)
                current_slug = alias[match] if match else None
            continue

        # It's a table.
        classes = (node.attributes.get("class") or "")
        if "wikitable" not in classes or not current_slug:
            continue
        players = _parse_squad_table(node)
        if players:
            rosters.setdefault(current_slug, [])
            existing = {p.name for p in rosters[current_slug]}
            rosters[current_slug].extend(p for p in players if p.name not in existing)

    log.info("Wikipedia: parsed rosters for %d teams", len(rosters))
    return rosters


def _parse_squad_table(table) -> list[Player]:
    players: list[Player] = []
    for row in table.css("tr"):
        cells = row.css("td")
        if len(cells) < 3:
            continue
        texts = [c.text(strip=True) for c in cells]
        # Find a position token among the first few cells.
        pos = ""
        for t in texts[:3]:
            mt = POS_RE.search(t)
            if mt:
                pos = mt.group(1).upper()[:2]
                break
        # Player name: first cell containing a link.
        name = ""
        for c in cells:
            link = c.css_first("a")
            if link and link.text(strip=True):
                name = link.text(strip=True)
                break
        if not name:
            continue
        # Club: last cell containing a link.
        club = ""
        for c in reversed(cells):
            link = c.css_first("a")
            if link and link.text(strip=True):
                club = link.text(strip=True)
                if club != name:
                    break
        # Caps / goals: trailing numeric cells.
        nums = [_int_or_none(t) for t in texts if _int_or_none(t) is not None]
        caps = nums[-2] if len(nums) >= 2 else None
        goals = nums[-1] if len(nums) >= 1 else None
        players.append(Player(name=name, position=pos, club=club, caps=caps, goals=goals))
    return players
