"""Ticket-price *estimates* for the knockout rounds (R16 onward).

There is no free, legitimate API that exposes live World Cup 2026 resale prices
(FIFA's platform is login/ToS-gated; SeatGeek + Ticketmaster gate prices behind
paid partner tiers — verified empirically). So this is a transparent MODEL
estimate, anchored on REAL public data and scaled by our own bracket prediction:

  predicted_get_in = stage_resale_base[stage]    (real: FIFA face value + published
                                                  resale get-in figures)
                   x venue_factor[city]          (real: NY/NJ, LA, Miami premium)
                   x demand_factor(teams)         (our bracket's expected teams +
                                                  host-nation / strength draw)
                   x time_factor(days_to_kickoff)

Anchors gathered via web search (June 2026): face value R16 $170-980, QF
$275-1,775, SF $420-3,295, Final $6,730->$8,680; resale get-in R16 Vancouver
~$1,900, QF Boston ~$2,350 / LA ~$2,950 / Miami ~$3,530, SF Dallas ~$3,530,
Final FIFA resale ~$9,200. Venues per match come from Ticketmaster (structural
data is ungated). Refresh anchors periodically — the app cannot web-search.
"""
from __future__ import annotations

from datetime import date

# match number -> (metro/city key, stadium) for the 32 knockout fixtures (73-104).
KNOCKOUT_VENUE: dict[int, tuple[str, str]] = {
    73: ("Los Angeles", "SoFi Stadium"),
    74: ("Boston", "Gillette Stadium"),
    75: ("Monterrey", "Estadio BBVA"),
    76: ("Houston", "NRG Stadium"),
    77: ("New York/NJ", "MetLife Stadium"),
    78: ("Dallas", "AT&T Stadium"),
    79: ("Mexico City", "Estadio Banorte"),
    80: ("Atlanta", "Mercedes-Benz Stadium"),
    81: ("San Francisco Bay", "Levi's Stadium"),
    82: ("Seattle", "Lumen Field"),
    83: ("Toronto", "BMO Field"),
    84: ("Los Angeles", "SoFi Stadium"),
    85: ("Vancouver", "BC Place Stadium"),
    86: ("Miami", "Hard Rock Stadium"),
    87: ("Kansas City", "GEHA Field at Arrowhead Stadium"),
    88: ("Dallas", "AT&T Stadium"),
    89: ("Philadelphia", "Lincoln Financial Field"),
    90: ("Houston", "NRG Stadium"),
    91: ("New York/NJ", "MetLife Stadium"),
    92: ("Mexico City", "Estadio Banorte"),
    93: ("Dallas", "AT&T Stadium"),
    94: ("Seattle", "Lumen Field"),
    95: ("Atlanta", "Mercedes-Benz Stadium"),
    96: ("Vancouver", "BC Place Stadium"),
    97: ("Boston", "Gillette Stadium"),
    98: ("Los Angeles", "SoFi Stadium"),
    99: ("Miami", "Hard Rock Stadium"),
    100: ("Kansas City", "GEHA Field at Arrowhead Stadium"),
    101: ("Dallas", "AT&T Stadium"),
    102: ("Atlanta", "Mercedes-Benz Stadium"),
    103: ("Miami", "Hard Rock Stadium"),
    104: ("New York/NJ", "MetLife Stadium"),
}

# Real published face-value range (USD, Category 4 -> Category 1) per stage.
FACE_VALUE: dict[str, tuple[int, int]] = {
    "round_of_16": (170, 980),
    "quarter_final": (275, 1775),
    "semi_final": (420, 3295),
    "third_place": (300, 1500),
    "final": (6730, 8680),
}

# Stage resale "get-in" baseline (USD) for an average-demand venue/matchup,
# anchored on the published resale figures above.
STAGE_RESALE_BASE: dict[str, int] = {
    "round_of_16": 1900,
    "quarter_final": 3000,
    "semi_final": 3800,
    "third_place": 1400,
    "final": 8500,
}

# Relative city demand multiplier (1.0 = average host city), from observed
# per-venue resale spreads + market size.
VENUE_FACTOR: dict[str, float] = {
    "New York/NJ": 1.35, "Los Angeles": 1.08, "Miami": 1.18, "Dallas": 1.05,
    "Boston": 0.85, "Kansas City": 1.0, "Atlanta": 0.95, "Seattle": 0.95,
    "Houston": 0.9, "San Francisco Bay": 1.0, "Philadelphia": 0.9,
    "Toronto": 0.95, "Vancouver": 0.9, "Mexico City": 1.05, "Monterrey": 0.82,
}

# Host nations (home demand) and globally large travelling fanbases.
HOST = {"united-states", "usa", "mexico", "canada"}
MARQUEE = {
    "brazil", "argentina", "england", "france", "germany", "spain",
    "portugal", "netherlands", "italy", "united-states", "mexico",
}

STAGE_OF = {  # match number -> stage
    **{n: "round_of_16" for n in range(89, 97)},
    **{n: "quarter_final" for n in range(97, 101)},
    101: "semi_final", 102: "semi_final", 103: "third_place", 104: "final",
}


def _draw(team_id: str | None, rating: float | None) -> float:
    """A 0..1-ish 'demand pull' for a team: on-pitch strength + off-pitch appeal."""
    if not team_id:
        return 0.35  # TBD slot — modest baseline demand
    r = rating if rating is not None else 1650.0
    base = max(0.0, min(1.0, (r - 1500) / 600))  # ratings ~1500-2100
    bonus = 0.0
    if team_id in HOST:
        bonus += 0.25
    if team_id in MARQUEE:
        bonus += 0.12
    return min(1.25, base + bonus)


def _time_factor(kickoff: str | None, today: date | None = None) -> float:
    """Prices firm up as kickoff nears: up to +35% inside the final month."""
    if not kickoff:
        return 1.0
    try:
        d = date.fromisoformat(kickoff[:10])
    except ValueError:
        return 1.0
    days = (d - (today or date.today())).days
    if days <= 0:
        return 1.35
    if days >= 30:
        return 1.0
    return 1.0 + (30 - days) / 30 * 0.35


def predict_ticket_prices(
    bracket: dict, ratings: dict[str, float], today: date | None = None
) -> list[dict]:
    """Estimated resale get-in price per knockout match, R16 onward. Uses the
    favourite bracket's expected teams for the demand term, so the estimate moves
    as the prediction moves."""
    rounds = ["round_of_16", "quarter_final", "semi_final", "final"]
    out: list[dict] = []
    for rnd in rounds:
        for tie in bracket.get(rnd, []):
            num = tie.get("number")
            if num is None or num not in KNOCKOUT_VENUE:
                continue
            stage = STAGE_OF.get(num, rnd)
            city, venue = KNOCKOUT_VENUE[num]
            vf = VENUE_FACTOR.get(city, 1.0)
            d_home = _draw(tie.get("home_id"), ratings.get(tie.get("home_id")))
            d_away = _draw(tie.get("away_id"), ratings.get(tie.get("away_id")))
            demand = 0.85 + (d_home + d_away) / 2 * 0.6  # ~0.85..1.45
            tf = _time_factor(tie.get("kickoff"), today)
            base = STAGE_RESALE_BASE[stage]
            predicted = round(base * vf * demand * tf / 5) * 5  # nearest $5
            fv = FACE_VALUE[stage]
            out.append({
                "number": num,
                "stage": stage,
                "city": city,
                "venue": venue,
                "kickoff": tie.get("kickoff"),
                "home": tie.get("home"),
                "away": tie.get("away"),
                "home_id": tie.get("home_id"),
                "away_id": tie.get("away_id"),
                "face_value_low": fv[0],
                "face_value_high": fv[1],
                "predicted_get_in": predicted,
                "demand_index": round(demand, 2),
                "venue_factor": vf,
            })
    out.sort(key=lambda t: t["number"])
    return out
