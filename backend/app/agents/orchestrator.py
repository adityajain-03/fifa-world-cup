"""Prediction orchestrator: scouts -> ratings -> simulation -> snapshot.

This is the multi-agent fan-out. Scout agents (one per team) run concurrently
to produce strength ratings; the deterministic model + Monte Carlo turn those
into probabilities; the Analyst agent writes the closing narrative.
"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

from .. import db
from ..config import settings
from ..models import BracketSnapshot, Match, MatchPrediction, ScoutDossier, Team
from ..model.ratings import TeamStrength, fifa_rank_to_rating, match_probabilities
from ..model.simulate import KO_ROUNDS, simulate
from .analyst import write_narrative
from .client import ClaudeClient
from .scout import scout_team

log = logging.getLogger("fifa.orchestrator")


def compute_data_version(teams: list[Team], matches: list[Match]) -> str:
    h = hashlib.sha256()
    for m in sorted(matches, key=lambda x: x.id):
        if m.status == "finished":
            h.update(f"{m.id}:{m.home_id}:{m.away_id}:{m.home_score}:{m.away_score}".encode())
    for t in sorted(teams, key=lambda x: x.id):
        names = ",".join(sorted(p.name for p in t.players))
        h.update(f"{t.id}:{t.group}:{t.fifa_rank}:{names}".encode())
    return h.hexdigest()[:16]


def _prior_dossier(team: Team) -> ScoutDossier:
    return ScoutDossier(
        rating=fifa_rank_to_rating(team.fifa_rank),
        one_line_outlook="FIFA-rank prior (set ANTHROPIC_API_KEY for Scout analysis).",
    )


def build_dossiers(
    client: ClaudeClient, teams: list[Team], matches: list[Match], data_version: str,
    *, force: bool = False,
) -> dict[str, ScoutDossier]:
    cached = db.get_dossiers()
    dossiers: dict[str, ScoutDossier] = {}
    to_scout: list[Team] = []

    for t in teams:
        row = cached.get(t.id)
        cached_dossier = None
        if row and row.get("data_version") == data_version:
            import json

            cached_dossier = ScoutDossier(**json.loads(row["payload_json"]))
        # Reuse a cached dossier only if it was genuinely news-grounded (has a
        # briefing). A prior-fallback (empty briefing) is re-scouted so a previous
        # timeout self-heals on the next refresh.
        grounded_cache = cached_dossier is not None and bool(cached_dossier.briefing)
        if not force and grounded_cache and client.available:
            dossiers[t.id] = cached_dossier
        elif client.available:
            to_scout.append(t)
        else:
            dossiers[t.id] = cached_dossier or _prior_dossier(t)

    if to_scout:
        log.info("Scouting %d teams (concurrency=%d)", len(to_scout), settings.scout_concurrency)
        with ThreadPoolExecutor(max_workers=settings.scout_concurrency) as pool:
            results = list(pool.map(lambda t: (t, scout_team(client, t, matches)), to_scout))
        for t, dossier in results:
            dossiers[t.id] = dossier or _prior_dossier(t)

    for tid, d in dossiers.items():
        db.store_dossier(tid, d, data_version)
    return dossiers


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def to_strengths(teams: list[Team], dossiers: dict[str, ScoutDossier]) -> list[TeamStrength]:
    out = []
    for t in teams:
        d = dossiers.get(t.id) or _prior_dossier(t)
        # Keep every team on the same sane Elo scale so a stray LLM outlier can't
        # dominate the simulation; blend lightly toward the FIFA-rank prior.
        prior = fifa_rank_to_rating(t.fifa_rank)
        rating = _clamp(d.rating, 1150.0, 2150.0)
        rating = 0.85 * rating + 0.15 * prior
        out.append(TeamStrength(
            id=t.id, name=t.name, rating=rating,
            attack_tilt=_clamp(d.attack_tilt, -1, 1), defense_tilt=_clamp(d.defense_tilt, -1, 1),
            group=t.group,
        ))
    return out


def compute_match_predictions(
    strengths: list[TeamStrength], matches: list[Match]
) -> list[MatchPrediction]:
    by_id = {s.id: s for s in strengths}
    preds: list[MatchPrediction] = []
    for m in matches:
        if not m.home_id or not m.away_id:
            continue
        a, b = by_id.get(m.home_id), by_id.get(m.away_id)
        if not a or not b:
            continue
        knockout = m.stage in KO_ROUNDS
        mp = match_probabilities(a, b, knockout=knockout, host_match=(m.stage == "group"))
        preds.append(MatchPrediction(
            match_id=m.id, p_home=mp.p_home, p_draw=mp.p_draw, p_away=mp.p_away,
            most_likely_score=mp.most_likely_score,
            expected_home_goals=mp.expected_home_goals,
            expected_away_goals=mp.expected_away_goals,
        ))
    return preds


def run_predictions(*, force: bool = False) -> BracketSnapshot:
    teams = db.get_teams()
    matches = db.get_matches()
    if not teams:
        raise RuntimeError("No teams in DB; run a crawl first.")

    data_version = compute_data_version(teams, matches)
    client = ClaudeClient()

    dossiers = build_dossiers(client, teams, matches, data_version, force=force)
    strengths = to_strengths(teams, dossiers)

    preds = compute_match_predictions(strengths, matches)
    db.store_match_predictions(preds, data_version)

    sim = simulate(strengths, matches, settings.monte_carlo_runs)
    odds_sorted = sorted(sim["odds"].values(), key=lambda o: o["win_title"], reverse=True)

    narrative = write_narrative(client, sim["odds"], sim["bracket"])

    snapshot = BracketSnapshot(
        created_at=db.now_iso(),
        data_version=data_version,
        grounded=client.available,
        odds=odds_sorted,
        bracket=sim["bracket"],
        group_predictions=sim["group_predictions"],
        analyst_narrative=narrative,
    )
    db.store_snapshot(snapshot)
    db.set_meta("last_prediction_at", snapshot.created_at)
    db.set_meta("data_version", data_version)
    log.info("Predictions complete (grounded=%s, champion=%s)",
             client.available, sim["bracket"].get("champion", {}).get("team"))
    return snapshot


def _cached_dossiers(teams: list[Team]) -> dict[str, ScoutDossier]:
    """Load stored dossiers (ratings) without any LLM calls; prior-fallback if missing."""
    import json

    rows = db.get_dossiers()
    out: dict[str, ScoutDossier] = {}
    for t in teams:
        row = rows.get(t.id)
        out[t.id] = ScoutDossier(**json.loads(row["payload_json"])) if row else _prior_dossier(t)
    return out


def run_simulation_only() -> BracketSnapshot:
    """Recompute match probabilities + bracket + odds from the CURRENT results
    using existing cached ratings. No crawling, no LLM — fast and free. Used by
    the live results poll so the bracket updates as matches finish.
    """
    teams = db.get_teams()
    matches = db.get_matches()
    if not teams:
        raise RuntimeError("No teams in DB; run a refresh first.")

    data_version = compute_data_version(teams, matches)
    dossiers = _cached_dossiers(teams)
    strengths = to_strengths(teams, dossiers)

    preds = compute_match_predictions(strengths, matches)
    db.store_match_predictions(preds, data_version)

    sim = simulate(strengths, matches, settings.monte_carlo_runs)
    odds_sorted = sorted(sim["odds"].values(), key=lambda o: o["win_title"], reverse=True)

    # Reuse the last narrative (analyst is an LLM call — skipped on the cheap path).
    prev = db.get_latest_snapshot() or {}
    grounded = any(d.briefing for d in dossiers.values())

    snapshot = BracketSnapshot(
        created_at=db.now_iso(),
        data_version=data_version,
        grounded=grounded,
        odds=odds_sorted,
        bracket=sim["bracket"],
        group_predictions=sim["group_predictions"],
        analyst_narrative=prev.get("analyst_narrative", ""),
    )
    db.store_snapshot(snapshot)
    db.set_meta("last_prediction_at", snapshot.created_at)
    db.set_meta("data_version", data_version)
    log.info("Re-simulated from cached ratings (champion=%s)",
             sim["bracket"].get("champion", {}).get("team"))
    return snapshot
