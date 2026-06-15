"""The daily pipeline: crawl -> store -> predict -> snapshot."""
from __future__ import annotations

import logging

import hashlib
import json

from .. import db
from ..agents.orchestrator import run_predictions, run_simulation_only
from ..crawlers import espn, news, wikipedia
from ..crawlers.seed import seed_teams

log = logging.getLogger("fifa.refresh")


def crawl_and_store() -> dict:
    """Refresh teams, matches, and rosters from public sources.

    ESPN is authoritative for fixtures/results and the group field; the seed is
    used only if ESPN is unreachable or returns an incomplete (<12-group) field.
    """
    notes = []
    teams: list = []

    # 1. Live matches & results from ESPN's JSON API; group field from Wikipedia
    #    (official A-L letters), falling back to ESPN round-robin composition.
    run_id = db.start_crawl_run("espn+wikipedia-groups")
    try:
        matches = espn.crawl_matches()
        official = wikipedia.crawl_groups()
        if len(official) == 12:
            teams = espn.field_from_groups(official)
            field_source = "wikipedia-official"
        else:
            teams = espn.build_field(matches)  # connected-components fallback
            field_source = "espn-components"
        espn.assign_match_groups(matches, teams)
        espn.assign_match_numbers(matches)  # official-style 1..N by kickoff order
        if len(teams) >= 48:
            db.upsert_teams(teams)
            db.upsert_matches(matches)
            notes.append(f"matches={len(matches)} teams={len(teams)} groups={field_source}")
            db.finish_crawl_run(run_id, "ok", notes[-1])
        else:
            raise RuntimeError(f"incomplete field ({len(teams)} teams)")
    except Exception as exc:  # noqa: BLE001
        log.warning("ESPN/Wikipedia crawl unusable (%s); falling back to seed", exc)
        db.finish_crawl_run(run_id, "error", str(exc))
        notes.append(f"crawl fallback: {exc}")
        if not db.get_teams():  # only seed if we have nothing
            teams = seed_teams()
            db.upsert_teams(teams)
        else:
            teams = db.get_teams()

    # 2. Squad rosters from Wikipedia (best-effort, enriches Scout + UI).
    run_id = db.start_crawl_run("wikipedia")
    try:
        rosters = wikipedia.crawl_squads(teams)
        enriched = []
        for t in teams:
            players = rosters.get(t.id)
            if players:
                t.players = players
                enriched.append(t)
        if enriched:
            db.upsert_teams(enriched)
        notes.append(f"wiki rosters={len(rosters)}")
        db.finish_crawl_run(run_id, "ok", notes[-1])
    except Exception as exc:  # noqa: BLE001
        log.exception("Wikipedia crawl failed")
        db.finish_crawl_run(run_id, "error", str(exc))
        notes.append(f"wiki error: {exc}")

    # 3. News headlines (ESPN) for the dashboard.
    try:
        headlines = news.crawl_news()
        if headlines:
            db.set_meta("news_json", json.dumps(headlines))
        notes.append(f"news={len(headlines)}")
    except Exception as exc:  # noqa: BLE001
        log.warning("News crawl failed: %s", exc)

    db.set_meta("last_crawl_at", db.now_iso())
    return {"notes": notes}


def run_refresh(*, force_predictions: bool = False) -> dict:
    """Full pipeline used by the manual refresh button: crawl everything (incl.
    news web search) + re-scout + simulate."""
    log.info("Refresh: crawling sources")
    crawl_result = crawl_and_store()
    log.info("Refresh: running predictions")
    snapshot = run_predictions(force=force_predictions)
    db.set_meta("results_hash", _results_hash(db.get_matches()))
    return {
        "crawl": crawl_result,
        "grounded": snapshot.grounded,
        "data_version": snapshot.data_version,
        "champion": snapshot.bracket.get("champion", {}).get("team")
        if isinstance(snapshot.bracket, dict) else None,
    }


def _results_hash(matches) -> str:
    h = hashlib.sha256()
    for m in sorted(matches, key=lambda x: x.id):
        if m.status in ("finished", "live"):
            h.update(f"{m.id}:{m.home_score}:{m.away_score}:{m.status}".encode())
    return h.hexdigest()[:16]


def poll_results() -> dict:
    """Cheap, LLM-free live update: fetch recent ESPN results; if any changed,
    re-simulate the bracket/odds from cached ratings. Runs frequently."""
    try:
        recent = espn.crawl_matches(dates=espn.recent_dates(days_back=1), ttl_hours=0.05)
        if recent:
            espn.assign_match_groups(recent, db.get_teams())  # keep group labels
            db.upsert_matches(recent)
    except Exception as exc:  # noqa: BLE001
        log.warning("Live results poll: crawl failed (%s)", exc)
        return {"updated": False, "reason": "crawl failed"}

    new_hash = _results_hash(db.get_matches())
    if new_hash == db.get_meta("results_hash"):
        return {"updated": False, "reason": "no change"}

    snapshot = run_simulation_only()
    db.set_meta("results_hash", new_hash)
    log.info("Live results changed → bracket/odds updated")
    return {
        "updated": True,
        "champion": snapshot.bracket.get("champion", {}).get("team")
        if isinstance(snapshot.bracket, dict) else None,
    }
