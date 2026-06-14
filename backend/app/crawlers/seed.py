"""Offline fallback for the 48-team / 12-group field.

Used ONLY when the live ESPN crawl is unreachable or returns an incomplete
field. The live crawl is authoritative. FIFA ranks come from `aliases`.
"""
from __future__ import annotations

from ..models import Team
from .aliases import fifa_rank_for, name_slug

# Plausible offline structure (not the official draw). Labelled clearly in the UI
# via the snapshot's `grounded`/crawl notes when this fallback is in effect.
SEED_GROUPS: dict[str, list[str]] = {
    "A": ["Argentina", "Croatia", "Ecuador", "South Korea"],
    "B": ["France", "Belgium", "Egypt", "Uzbekistan"],
    "C": ["Spain", "Switzerland", "Ivory Coast", "Jordan"],
    "D": ["England", "Australia", "Norway", "Panama"],
    "E": ["Brazil", "Senegal", "Scotland", "Saudi Arabia"],
    "F": ["Portugal", "Austria", "Paraguay", "New Zealand"],
    "G": ["Germany", "Morocco", "Japan", "Cape Verde"],
    "H": ["Netherlands", "Colombia", "Qatar", "Curacao"],
    "I": ["Uruguay", "United States", "Ghana", "Haiti"],
    "J": ["Mexico", "Iran", "Tunisia", "South Africa"],
    "K": ["Canada", "Sweden", "Algeria", "Iraq"],
    "L": ["Italy", "Turkey", "Nigeria", "Honduras"],
}


def seed_teams() -> list[Team]:
    teams: list[Team] = []
    for group, members in SEED_GROUPS.items():
        for name in members:
            teams.append(Team(
                id=name_slug(name), name=name, group=group,
                fifa_rank=fifa_rank_for(name),
            ))
    return teams
