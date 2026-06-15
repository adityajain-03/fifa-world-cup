"""Monte Carlo tournament simulation.

Given team strengths (from Scout ratings, or FIFA-rank priors) and the matches
already played, simulate the whole tournament N times to produce per-team
advancement and title probabilities, plus a deterministic "favourite" bracket
for display.

The knockout bracket follows the **official 2026 FIFA slot map** (see
`bracket_map.py`, verified against ESPN's published fixtures): group winners,
runners-up, and the 8 best third-placed teams are placed into fixed R32 slots
(e.g. R32 match 1 is "Group A 2nd v Group B 2nd"), and winners advance through
the fixed tree. Group results already played are always respected.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass

from ..models import Match
from . import bracket_map as bm
from .ratings import MatchProb, TeamStrength, match_probabilities

KO_ROUNDS = ["round_of_32", "round_of_16", "quarter_final", "semi_final", "final"]


@dataclass
class _Finished:
    home_id: str
    away_id: str
    home_score: int
    away_score: int


def _sample_poisson(lam: float) -> int:
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


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
            return _Finished(a, b, f.away_score, f.home_score)
        return None

    def _group(self, tid: str) -> str | None:
        t = self.teams.get(tid)
        return t.group if t else None

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

    # -- official knockout bracket --------------------------------------
    def _qualifiers(self, orders: dict[str, list[str]]) -> tuple[dict, dict, dict]:
        """From each group's finishing order, return winners{group}, runners{group}
        and the third-slot assignment {r32_index: team_id} for the best 8 thirds."""
        winners = {g: o[0] for g, o in orders.items() if len(o) >= 1}
        runners = {g: o[1] for g, o in orders.items() if len(o) >= 2}
        thirds = {g: o[2] for g, o in orders.items() if len(o) >= 3}
        # Best 8 thirds by rating (proxy for the real pts/gd/gf ranking).
        best = sorted(thirds, key=lambda g: self.teams[thirds[g]].rating, reverse=True)[:8]
        qualified = {g: thirds[g] for g in best}
        assigned = bm.assign_thirds(qualified)
        return winners, runners, assigned

    def _resolve_r32(self, winners: dict, runners: dict, thirds: dict) -> list[tuple]:
        pairs = []
        for idx, (home_slot, away_slot) in enumerate(bm.R32_SLOTS, start=1):
            pairs.append((
                self._slot_team(home_slot, winners, runners, thirds, idx),
                self._slot_team(away_slot, winners, runners, thirds, idx),
            ))
        return pairs

    @staticmethod
    def _slot_team(slot, winners, runners, thirds, idx):
        kind = slot[0]
        if kind == "W":
            return winners.get(slot[1])
        if kind == "R":
            return runners.get(slot[1])
        return thirds.get(idx)  # "T" — assigned by r32 match index

    def _winner(self, a: str | None, b: str | None, sample: bool) -> str | None:
        if not a or not b:
            return a or b
        mp = self._prob(a, b, knockout=True)
        if sample:
            return a if random.random() < mp.advance_home else b
        return a if mp.advance_home >= mp.advance_away else b

    def _play(self, r32_pairs: list[tuple], sample: bool) -> dict:
        """Advance the official tree; return {round: set(team_ids)} + champion."""
        r32_w = {i: self._winner(a, b, sample) for i, (a, b) in enumerate(r32_pairs, 1)}
        r16_w = {j: self._winner(r32_w[x], r32_w[y], sample)
                 for j, (x, y) in enumerate(bm.R16_PAIRS, 1)}
        qf_w = {k: self._winner(r16_w[x], r16_w[y], sample)
                for k, (x, y) in enumerate(bm.QF_PAIRS, 1)}
        sf_w = {l: self._winner(qf_w[x], qf_w[y], sample)
                for l, (x, y) in enumerate(bm.SF_PAIRS, 1)}
        champ = self._winner(sf_w[bm.FINAL_PAIR[0]], sf_w[bm.FINAL_PAIR[1]], sample)
        participants = {t for pair in r32_pairs for t in pair if t}
        return {
            "round_of_32": participants,
            "round_of_16": set(v for v in r32_w.values() if v),
            "quarter_final": set(v for v in r16_w.values() if v),
            "semi_final": set(v for v in qf_w.values() if v),
            "final": set(v for v in sf_w.values() if v),
            "champion": champ,
        }

    # -- public ----------------------------------------------------------
    def run(self) -> dict:
        title = defaultdict(int)
        reach = {r: defaultdict(int) for r in KO_ROUNDS}
        win_group = defaultdict(int)
        advance = defaultdict(int)

        for _ in range(self.runs):
            orders = {g: self._sim_group(g) for g in self.groups}
            for o in orders.values():
                if o:
                    win_group[o[0]] += 1
            winners, runners, thirds = self._qualifiers(orders)
            qualifiers = set(winners.values()) | set(runners.values()) | set(thirds.values())
            for q in qualifiers:
                advance[q] += 1
            if len(qualifiers) < 2:
                continue
            reached = self._play(self._resolve_r32(winners, runners, thirds), sample=True)
            if reached["champion"]:
                title[reached["champion"]] += 1
            for r in reach:
                for tid in reached[r]:
                    reach[r][tid] += 1

        runs = self.runs
        odds = {}
        for tid, t in self.teams.items():
            odds[tid] = {
                "team_id": tid, "team_name": t.name, "group": t.group,
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

    # -- deterministic favourite bracket --------------------------------
    def _tie(self, a: str | None, b: str | None) -> tuple[dict, str | None]:
        def info(tid):
            t = self.teams.get(tid) if tid else None
            return (t.name if t else "TBD"), (t.group if t else None)
        if not a or not b:
            w = a or b
            name, grp = info(w)
            return {"home": info(a)[0], "home_id": a, "home_group": info(a)[1],
                    "away": info(b)[0], "away_id": b, "away_group": info(b)[1],
                    "winner": name, "winner_id": w, "winner_group": grp,
                    "p_home_advance": 1.0 if a else 0.0}, w
        mp = self._prob(a, b, knockout=True)
        winner = a if mp.advance_home >= mp.advance_away else b
        na, ga = info(a); nb, gb = info(b); nw, gw = info(winner)
        return {
            "home": na, "home_id": a, "home_group": ga,
            "away": nb, "away_id": b, "away_group": gb,
            "winner": nw, "winner_id": winner, "winner_group": gw,
            "p_home_advance": round(mp.advance_home, 3),
        }, winner

    def favourite_bracket(self) -> dict:
        orders = {g: self._expected_group_order(g) for g in self.groups}
        winners, runners, thirds = self._qualifiers(orders)
        r32_pairs = self._resolve_r32(winners, runners, thirds)
        if sum(1 for a, b in r32_pairs if a and b) == 0:
            return {}

        r32_ties, r32_w = [], {}
        for i, (a, b) in enumerate(r32_pairs, 1):
            tie, w = self._tie(a, b)
            home_slot, away_slot = bm.R32_SLOTS[i - 1]
            tie["home_slot"] = bm.slot_label(home_slot)
            tie["away_slot"] = bm.slot_label(away_slot)
            tie["match_no"] = i
            r32_ties.append(tie); r32_w[i] = w
        r16_ties, r16_w = [], {}
        for j, (x, y) in enumerate(bm.R16_PAIRS, 1):
            tie, w = self._tie(r32_w[x], r32_w[y]); r16_ties.append(tie); r16_w[j] = w
        qf_ties, qf_w = [], {}
        for k, (x, y) in enumerate(bm.QF_PAIRS, 1):
            tie, w = self._tie(r16_w[x], r16_w[y]); qf_ties.append(tie); qf_w[k] = w
        sf_ties, sf_w = [], {}
        for l, (x, y) in enumerate(bm.SF_PAIRS, 1):
            tie, w = self._tie(qf_w[x], qf_w[y]); sf_ties.append(tie); sf_w[l] = w
        final_tie, champ = self._tie(sf_w[bm.FINAL_PAIR[0]], sf_w[bm.FINAL_PAIR[1]])

        # Reorder each round into tree (top-to-bottom) order so the columns align
        # as a bracket: each match sits between the two feeders that produced it.
        def order(ties, display):
            return [ties[i - 1] for i in display]

        ct = self.teams.get(champ)
        return {
            "round_of_32": order(r32_ties, bm.R32_DISPLAY),
            "round_of_16": order(r16_ties, bm.R16_DISPLAY),
            "quarter_final": order(qf_ties, bm.QF_DISPLAY),
            "semi_final": order(sf_ties, bm.SF_DISPLAY),
            "final": [final_tie],
            "champion": {"team_id": champ, "team": ct.name if ct else "TBD",
                         "group": ct.group if ct else None},
        }

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
                    "team_id": i, "team_name": self.teams[i].name,
                    "expected_points": round(pts[i], 2),
                    "win_group": round(odds[i]["win_group"], 3),
                    "advance": round(odds[i]["advance_group"], 3),
                }
                for i in ordered
            ]
        return out


def simulate(teams: list[TeamStrength], matches: list[Match], runs: int) -> dict:
    return Simulator(teams, matches, runs).run()
