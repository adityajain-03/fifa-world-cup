"""Deterministic match-probability model: Elo expectancy + Poisson scorelines.

The LLM Scout agents produce the *ratings*; this module turns a rating gap
into calibrated, internally consistent per-match probabilities. No LLM here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Tunable constants -------------------------------------------------------
WC_BASELINE_GOALS = 2.6      # avg total goals in a World Cup match
SUPREMACY_SCALE = 3.0        # maps Elo expectancy spread -> goal supremacy
TILT_WEIGHT = 0.15           # how much attack/defense tilt shifts expected goals
HOST_ELO_BONUS = 35.0        # small home bump for host nations
MAX_GOALS = 8                # Poisson grid ceiling

HOST_TEAM_IDS = {"united-states", "mexico", "canada"}


@dataclass
class TeamStrength:
    id: str
    name: str
    rating: float
    attack_tilt: float = 0.0
    defense_tilt: float = 0.0
    group: str | None = None


@dataclass
class MatchProb:
    p_home: float
    p_draw: float
    p_away: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: str
    # knockout: probability the home/away side advances (incl. penalties)
    advance_home: float = 0.0
    advance_away: float = 0.0


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def expected_goals(home: TeamStrength, away: TeamStrength, *, host_match: bool = False) -> tuple[float, float]:
    r_home = home.rating + (HOST_ELO_BONUS if (host_match and home.id in HOST_TEAM_IDS) else 0.0)
    r_away = away.rating
    e_home = 1.0 / (1.0 + 10 ** (-(r_home - r_away) / 400.0))
    supremacy = SUPREMACY_SCALE * (e_home - 0.5)
    lam_home = (WC_BASELINE_GOALS + supremacy) / 2.0
    lam_away = (WC_BASELINE_GOALS - supremacy) / 2.0
    lam_home *= 1.0 + TILT_WEIGHT * (home.attack_tilt - away.defense_tilt)
    lam_away *= 1.0 + TILT_WEIGHT * (away.attack_tilt - home.defense_tilt)
    return max(0.15, lam_home), max(0.15, lam_away)


def match_probabilities(
    home: TeamStrength,
    away: TeamStrength,
    *,
    knockout: bool = False,
    host_match: bool = False,
) -> MatchProb:
    lam_home, lam_away = expected_goals(home, away, host_match=host_match)
    home_pmf = [_poisson_pmf(i, lam_home) for i in range(MAX_GOALS + 1)]
    away_pmf = [_poisson_pmf(j, lam_away) for j in range(MAX_GOALS + 1)]

    p_home = p_draw = p_away = 0.0
    best_p, best_score = -1.0, "0-0"
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = home_pmf[i] * away_pmf[j]
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
            if p > best_p:
                best_p, best_score = p, f"{i}-{j}"

    total = p_home + p_draw + p_away
    p_home, p_draw, p_away = p_home / total, p_draw / total, p_away / total

    mp = MatchProb(
        p_home=p_home, p_draw=p_draw, p_away=p_away,
        expected_home_goals=round(lam_home, 2), expected_away_goals=round(lam_away, 2),
        most_likely_score=best_score,
    )
    if knockout:
        # Split the draw mass via a penalty-shootout edge for the stronger side.
        pen_home = 0.5 + max(-0.2, min(0.2, (home.rating - away.rating) / 2000.0))
        mp.advance_home = p_home + p_draw * pen_home
        mp.advance_away = p_away + p_draw * (1 - pen_home)
    return mp


def fifa_rank_to_rating(rank: int | None) -> float:
    """Prior rating from a FIFA ranking position (used when ungrounded)."""
    if not rank:
        return 1500.0
    # Rank 1 ~ 2050, rank ~50 ~ 1500, tapering for minnows.
    return max(1300.0, 2050.0 - 11.0 * (rank - 1))
