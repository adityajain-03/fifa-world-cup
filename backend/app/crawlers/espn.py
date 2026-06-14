"""Live matches & results from ESPN's public soccer JSON API, plus deriving the
group field from the real fixtures.

ESPN exposes a stable, key-free JSON endpoint for the World Cup
(`fifa.world` league). We consume that rather than scraping HTML. ESPN does not
label matches with a group letter, so group *composition* is recovered from the
round-robin structure (teams that face each other in the group stage form a
group), and letters are assigned by the strongest team in each group.
"""
from __future__ import annotations

import logging
import string
from collections import defaultdict
from datetime import date, timedelta

from ..models import Match, Stage, Team
from .aliases import canonical, fifa_rank_for, is_placeholder, name_slug
from .base import fetch_json

log = logging.getLogger("fifa.crawl.espn")

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

TOURNAMENT_START = date(2026, 6, 11)
TOURNAMENT_END = date(2026, 7, 19)

STAGE_BY_DATE: list[tuple[date, date, Stage]] = [
    (date(2026, 6, 11), date(2026, 6, 27), "group"),
    (date(2026, 6, 28), date(2026, 7, 3), "round_of_32"),
    (date(2026, 7, 4), date(2026, 7, 7), "round_of_16"),
    (date(2026, 7, 9), date(2026, 7, 11), "quarter_final"),
    (date(2026, 7, 14), date(2026, 7, 15), "semi_final"),
    (date(2026, 7, 18), date(2026, 7, 18), "third_place"),
    (date(2026, 7, 19), date(2026, 7, 19), "final"),
]


def _stage_for(d: date) -> Stage:
    for start, end, stage in STAGE_BY_DATE:
        if start <= d <= end:
            return stage
    return "group"


def _status(state: str, completed: bool) -> str:
    if completed or state == "post":
        return "finished"
    if state == "in":
        return "live"
    return "scheduled"


def crawl_matches() -> list[Match]:
    matches: dict[str, Match] = {}
    d = TOURNAMENT_START
    while d <= TOURNAMENT_END:
        try:
            data = fetch_json(SCOREBOARD, params={"dates": d.strftime("%Y%m%d")}, ttl_hours=1.0)
        except Exception:  # noqa: BLE001
            d += timedelta(days=1)
            continue
        for ev in data.get("events", []):
            try:
                m = _parse_event(ev, d)
            except Exception:  # noqa: BLE001
                log.debug("skip unparseable ESPN event %s", ev.get("id"))
                continue
            if m:
                matches[m.id] = m
        d += timedelta(days=1)
    log.info("ESPN: parsed %d matches", len(matches))
    return list(matches.values())


def _parse_event(ev: dict, d: date) -> Match | None:
    comp = (ev.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    if len(competitors) != 2:
        return None
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

    status = comp.get("status") or ev.get("status") or {}
    stype = status.get("type") or {}

    def team_name(c: dict) -> str:
        t = c.get("team") or {}
        return t.get("displayName") or t.get("name") or t.get("shortDisplayName") or "?"

    def score(c: dict):
        s = c.get("score")
        try:
            return int(s)
        except (TypeError, ValueError):
            return None

    hname, aname = team_name(home), team_name(away)
    h_ph, a_ph = is_placeholder(hname), is_placeholder(aname)
    stage = _stage_for(d)
    # A placeholder competitor means a knockout fixture with TBD teams; never group.
    if (h_ph or a_ph) and stage == "group":
        stage = "round_of_32"

    return Match(
        id=f"espn-{ev.get('id')}",
        stage=stage,
        group=None,
        date=(ev.get("date") or d.isoformat())[:10],
        home_id=None if h_ph else name_slug(hname),
        away_id=None if a_ph else name_slug(aname),
        home_name=hname,
        away_name=aname,
        home_score=score(home),
        away_score=score(away),
        status=_status(stype.get("state", "pre"), bool(stype.get("completed"))),  # type: ignore[arg-type]
    )


def field_from_groups(groups: dict[str, list[str]]) -> list[Team]:
    """Build the 48 teams from an authoritative {letter: [names]} mapping
    (e.g. Wikipedia's official groups). Slugs align with ESPN match team ids.
    """
    teams: list[Team] = []
    for letter, names in groups.items():
        for nm in names:
            teams.append(Team(
                id=name_slug(nm), name=canonical(nm), group=letter,
                fifa_rank=fifa_rank_for(nm),
            ))
    return teams


def assign_match_groups(matches: list[Match], teams: list[Team]) -> None:
    """Set `group` on group-stage matches from the teams' group letters."""
    slug_letter = {t.id: t.group for t in teams}
    for m in matches:
        if m.stage == "group" and m.home_id in slug_letter:
            m.group = slug_letter[m.home_id]
        elif m.stage == "group" and m.away_id in slug_letter:
            m.group = slug_letter[m.away_id]


def build_field(matches: list[Match]) -> list[Team]:
    """Recover the 12 groups (composition + letters) from real group fixtures and
    set `match.group` on those fixtures. Returns the 48 Team objects.
    """
    # union-find over group-stage matches with two real teams
    parent: dict[str, str] = {}
    names: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    for m in matches:
        if m.stage == "group" and m.home_id and m.away_id \
                and not is_placeholder(m.home_name) and not is_placeholder(m.away_name):
            union(m.home_id, m.away_id)
            names[m.home_id] = m.home_name
            names[m.away_id] = m.away_name

    comps: dict[str, list[str]] = defaultdict(list)
    for tid in names:
        comps[find(tid)].append(tid)
    groups = [members for members in comps.values() if len(members) == 4]
    if len(groups) < 12:
        log.warning("ESPN: only %d full groups recovered; field may be incomplete", len(groups))

    # Assign letters by the best (lowest) FIFA rank in each group.
    def best_rank(members: list[str]) -> int:
        ranks = [fifa_rank_for(names[t]) or 999 for t in members]
        return min(ranks)

    groups.sort(key=best_rank)
    team_group: dict[str, str] = {}
    teams: list[Team] = []
    for idx, members in enumerate(groups[:12]):
        letter = string.ascii_uppercase[idx]
        for tid in sorted(members, key=lambda t: fifa_rank_for(names[t]) or 999):
            team_group[tid] = letter
            teams.append(Team(
                id=tid, name=names[tid], group=letter,
                fifa_rank=fifa_rank_for(names[tid]),
            ))

    # Backfill group on the group-stage matches.
    for m in matches:
        if m.stage == "group" and m.home_id in team_group:
            m.group = team_group[m.home_id]

    log.info("ESPN: built field of %d teams across %d groups", len(teams), len(groups[:12]))
    return teams
