"""Name normalisation, slugs, FIFA-rank priors, and placeholder detection.

Shared by the crawlers so team identities are consistent regardless of which
source (ESPN names, Wikipedia headings) a name comes from.
"""
from __future__ import annotations

import re

# Map common name variants to a canonical display name.
NAME_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "korea republic": "South Korea",
    "republic of korea": "South Korea",
    "ir iran": "Iran",
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "czech republic": "Czechia",
    "dr congo": "Congo DR",
    "democratic republic of the congo": "Congo DR",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "bosnia and herzegovina": "Bosnia-Herzegovina",
    "holland": "Netherlands",
}

# Approximate FIFA ranking positions used as rating priors (ungrounded fallback
# and as the Scout's starting point). Not authoritative; the Scout adjusts them.
FIFA_RANKS = {
    "argentina": 1, "france": 2, "spain": 3, "england": 4, "brazil": 5,
    "portugal": 6, "netherlands": 7, "belgium": 8, "germany": 9, "croatia": 10,
    "uruguay": 11, "morocco": 12, "colombia": 14, "japan": 15, "united states": 16,
    "mexico": 17, "senegal": 18, "switzerland": 19, "iran": 21, "austria": 22,
    "south korea": 23, "ecuador": 24, "sweden": 25, "australia": 26, "canada": 30,
    "egypt": 32, "norway": 33, "scotland": 38, "panama": 39, "paraguay": 40,
    "ivory coast": 41, "tunisia": 45, "turkey": 26, "algeria": 36, "qatar": 51,
    "congo dr": 56, "uzbekistan": 57, "south africa": 58, "iraq": 58,
    "saudi arabia": 60, "jordan": 64, "cape verde": 70, "ghana": 73,
    "bosnia-herzegovina": 74, "curacao": 82, "haiti": 83, "new zealand": 86,
}

_PLACEHOLDER_RE = re.compile(r"winner|runner|place|group\s+[a-l]\b|tbd|qualifier", re.I)


def slugify(name: str) -> str:
    s = name.lower().strip()
    # strip accents crudely
    s = s.replace("ç", "c").replace("ã", "a").replace("é", "e").replace("í", "i")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def canonical(name: str) -> str:
    return NAME_ALIASES.get(name.lower().strip(), name.strip())


def name_slug(name: str) -> str:
    return slugify(canonical(name))


def fifa_rank_for(name: str):
    return FIFA_RANKS.get(canonical(name).lower())


def is_placeholder(name: str | None) -> bool:
    return bool(name and _PLACEHOLDER_RE.search(name))
