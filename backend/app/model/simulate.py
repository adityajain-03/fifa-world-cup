"""Monte Carlo tournament simulation.

Given team strengths (from Scout ratings, or FIFA-rank priors) and the matches
already played, simulate the whole tournament N times to produce per-team
advancement and title probabilities, plus a deterministic "favourite" bracket
for display.

The knockout bracket is *rating-seeded* (standard 1-vs-32 seeding of the 32
qualifiers) rather than the official FIFA slot map — the official slotting
depends on which third-placed teams advance and is intricate; a rating-seeded
single-elimination bracket is reproducible and well-balanced. Group results
that have already happened are always respected.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass

from ..models import Match
from .ratings import MatchProb, TeamStrength, match_probabilities

KO_ROUNDS = ["round_of_32", "round_of_16", "quarter_final", "semi_final", "final"]


@dataclass
class _Finished:
    home_id: str
    away_id: str
    home_score: int
    away_score: int


def _sample_poisson(lam: float) -> int:
    # Knuth's algorithm; fine for the small lambdas (~1-2) used here.
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def _seed_order(n: int) -> list[int]:
    """Standard single-elimination seeding order for a bracket of size n."""
    if n == 1:
        return [1]
    prev = _seed_order(n // 2)
    out: list[int] = []
    for s in prev:
        out.append(s)
        out.append(n + 1 - s)
    return out


class Simulator:
    def __init__(self, teams: list[TeamStrength], matches: list[Match], runs: int):
        self.runs = runs
        self.teams = {t.id: t for t in teams}
        self.groups: dict[str, list[str]] = defaultdict(list)
        for t in teams:
            if t.group:
                self.groups[t.group].append(t.id)
        self.finished_group = self._finished_group(matches)
        self._prob_cache: dict[tuple[str, str, bool], MatchProb] = {}

    # -- helpers ---------------------------------------------------------
    def _finished_group(self, matches: list[Match]) -> dict[tuple[str, str], _Finished]:
        out: dict[tuple[str, str], _Finished] = {}
        for m in matches:
            if (
                m.stage == "group"
                and m.status == "finished"
                and m.home_id in self.teams
                and m.away_id in self.teams
                and m.home_score is not None
                and m.away_score is not None
            ):
                out[(m.home_id, m.away_id)] = _Finished(
                    m.home_id, m.away_id, m.home_score, m.away_score
                )
        return out

    def _prob(self, a: str, b: str, knockout: bool) -> MatchProb:
        key = (a, b, knockout)
        if key not in self._prob_cache:
            self._prob_cache[key] = match_probabilities(
                self.teams[a], self.teams[b], knockout=knockout
            )
        return self._prob_cache[key]

    def _finished_for(self, a: str, b: str) -> _Finished | None:
        if (a, b) in self.finished_group:
            return self.finished_group[(a, b)]
        if (b, a) in self.finished_group:
            f = self.finished_group[(b, a)]
            return _Finished(a, b, f.away_score, f.home_score)  # flip orientation
        return None

    # -- group stage -----------------------------------------------------
    def _sim_group(self, group: str) -> list[str]:
        ids = self.groups[group]
        pts = {i: 0 for i in ids}
        gd = {i: 0 for i in ids}
        gf = {i: 0 for i in ids}
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = ids[x], ids[y]
                fin = self._finished_for(a, b)
                if fin:
                    hs, as_ = fin.home_score, fin.away_score
                else:
                    mp = self._prob(a, b, knockout=False)
                    hs = _sample_poisson(mp.expected_home_goals)
                    as_ = _sample_poisson(mp.expected_away_goals)
                gf[a] += hs; gf[b] += as_
                gd[a] += hs - as_; gd[b] += as_ - hs
                if hs > as_:
                    pts[a] += 3
                elif hs < as_:
                    pts[b] += 3
                else:
                    pts[a] += 1; pts[b] += 1
        return sorted(ids, key=lambda i: (pts[i], gd[i], gf[i]), reverse=True)

    def _sim_knockout(self, qualifiers: list[str]) -> dict:
        """Single elimination over rating-seeded qualifiers. Returns reached map."""
        seeds = sorted(qualifiers, key=lambda i: self.teams[i].rating, reverse=True)
        order = _seed_order(len(seeds))
        bracket = [seeds[s - 1] for s in order]
        reached = {"round_of_32": list(bracket)}
        round_idx = 0
        while len(bracket) > 1:
            nxt: list[str] = []
            for i in range(0, len(bracket), 2):
                a, b = bracket[i], bracket[i + 1]
                mp = self._prob(a, b, knockout=True)
                nxt.append(a if random.random() < mp.advance_home else b)
            bracket = nxt
            round_idx += 1
            if round_idx < len(KO_ROUNDS):
                reached[KO_ROUNDS[round_idx]] = list(bracket)
        reached["champion"] = bracket[0]
        return reached

    # -- public ----------------------------------------------------------
    def run(self) -> dict:
        title = defaultdict(int)
        reach = {r: defaultdict(int) for r in ["round_of_32", "round_of_16",
                                               "quarter_final", "semi_final", "final"]}
        win_group = defaultdict(int)
        advance = defaultdict(int)

        for _ in range(self.runs):
            winners, runners, thirds = [], [], []
            for g in sorted(self.groups):
                order = self._sim_group(g)
                if len(order) >= 1:
                    winners.append(order[0]); win_group[order[0]] += 1
                if len(order) >= 2:
                    runners.append(order[1])
                if len(order) >= 3:
                    thirds.append(order[2])
            # best 8 thirds by rating as a proxy (real tiebreak is pts/gd/gf,
            # but within a single sampled run rating ordering is a fair stand-in)
            best_thirds = sorted(thirds, key=lambda i: self.teams[i].rating, reverse=True)[:8]
            qualifiers = winners + runners + best_thirds
            for q in qualifiers:
                advance[q] += 1
            # pad to a power of two if a partial field (shouldn't happen at 32)
            n = 1 << (len(qualifiers) - 1).bit_length() if qualifiers else 0
            while len(qualifiers) < n:
                qualifiers.append(qualifiers[-1])
            if len(qualifiers) < 2:
                continue
            reached = self._sim_knockout(qualifiers)
            title[reached["champion"]] += 1
            for r in reach:
                for tid in set(reached.get(r, [])):
                    reach[r][tid] += 1

        runs = self.runs
        odds = {}
        for tid, t in self.teams.items():
            odds[tid] = {
                "team_id": tid,
                "team_name": t.name,
                "rating": round(t.rating, 1),
                "win_title": title[tid] / runs,
                "reach_final": reach["final"][tid] / runs,
                "reach_semi": reach["semi_final"][tid] / runs,
                "reach_quarter": reach["quarter_final"][tid] / runs,
                "reach_r16": reach["round_of_16"][tid] / runs,
                "reach_r32": reach["round_of_32"][tid] / runs,
                "win_group": win_group[tid] / runs,
                "advance_group": advance[tid] / runs,
            }
        return {
            "odds": odds,
            "bracket": self.favourite_bracket(),
            "group_predictions": self.group_table_predictions(odds),
        }

    # -- deterministic favourite bracket & group tables ------------------
    def favourite_bracket(self) -> dict:
        """Most-likely path: the favourite advances at every step."""
        winners, runners, thirds = [], [], []
        for g in sorted(self.groups):
            order = self._expected_group_order(g)
            if order:
                winners.append(order[0])
            if len(order) > 1:
                runners.append(order[1])
            if len(order) > 2:
                thirds.append((order[2], self.teams[order[2]].rating))
        best_thirds = [t for t, _ in sorted(thirds, key=lambda x: x[1], reverse=True)[:8]]
        qualifiers = winners + runners + best_thirds
        if len(qualifiers) < 2:
            return {}
        seeds = sorted(qualifiers, key=lambda i: self.teams[i].rating, reverse=True)
        order = _seed_order(len(seeds))
        bracket_ids = [seeds[s - 1] for s in order]

        rounds: dict[str, list] = {}
        ridx = 0
        while len(bracket_ids) > 1:
            ties = []
            nxt = []
            for i in range(0, len(bracket_ids), 2):
                a, b = bracket_ids[i], bracket_ids[i + 1]
                mp = self._prob(a, b, knockout=True)
                winner = a if mp.advance_home >= mp.advance_away else b
                ties.append({
                    "home": self.teams[a].name, "home_id": a,
                    "away": self.teams[b].name, "away_id": b,
                    "winner": self.teams[winner].name, "winner_id": winner,
                    "p_home_advance": round(mp.advance_home, 3),
                })
                nxt.append(winner)
            rounds[KO_ROUNDS[ridx]] = ties
            bracket_ids = nxt
            ridx += 1
        rounds["champion"] = {
            "team_id": bracket_ids[0],
            "team": self.teams[bracket_ids[0]].name,
        }
        return rounds

    def _expected_group_order(self, group: str) -> list[str]:
        ids = self.groups[group]
        pts = {i: 0.0 for i in ids}
        gd = {i: 0.0 for i in ids}
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = ids[x], ids[y]
                fin = self._finished_for(a, b)
                if fin:
                    hs, as_ = fin.home_score, fin.away_score
                    if hs > as_:
                        pts[a] += 3
                    elif hs < as_:
                        pts[b] += 3
                    else:
                        pts[a] += 1; pts[b] += 1
                    gd[a] += hs - as_; gd[b] += as_ - hs
                else:
                    mp = self._prob(a, b, knockout=False)
                    pts[a] += 3 * mp.p_home + mp.p_draw
                    pts[b] += 3 * mp.p_away + mp.p_draw
                    gd[a] += mp.expected_home_goals - mp.expected_away_goals
                    gd[b] += mp.expected_away_goals - mp.expected_home_goals
        return sorted(ids, key=lambda i: (pts[i], gd[i]), reverse=True)

    def group_table_predictions(self, odds: dict) -> dict:
        out: dict[str, list] = {}
        for g in sorted(self.groups):
            ids = self.groups[g]
            pts = {i: 0.0 for i in ids}
            for x in range(len(ids)):
                for y in range(x + 1, len(ids)):
                    a, b = ids[x], ids[y]
                    fin = self._finished_for(a, b)
                    if fin:
                        if fin.home_score > fin.away_score:
                            pts[a] += 3
                        elif fin.home_score < fin.away_score:
                            pts[b] += 3
                        else:
                            pts[a] += 1; pts[b] += 1
                    else:
                        mp = self._prob(a, b, knockout=False)
                        pts[a] += 3 * mp.p_home + mp.p_draw
                        pts[b] += 3 * mp.p_away + mp.p_draw
            ordered = sorted(ids, key=lambda i: pts[i], reverse=True)
            out[g] = [
                {
                    "team_id": i,
                    "team_name": self.teams[i].name,
                    "expected_points": round(pts[i], 2),
                    "win_group": round(odds[i]["win_group"], 3),
                    "advance": round(odds[i]["advance_group"], 3),
                }
                for i in ordered
            ]
        return out


def simulate(teams: list[TeamStrength], matches: list[Match], runs: int) -> dict:
    return Simulator(teams, matches, runs).run()
