"""REST API for the dashboard."""
from __future__ import annotations

import json
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query

from .. import db
from ..agents.orchestrator import whatif_bracket
from ..config import settings
from ..services.refresh import run_refresh

log = logging.getLogger("fifa.api")
router = APIRouter()

# Simple single-flight guard so concurrent /refresh calls don't pile up.
_refresh_lock = threading.Lock()
_refresh_running = {"value": False}


def _do_refresh() -> None:
    try:
        run_refresh()
    except Exception:  # noqa: BLE001
        log.exception("Refresh failed")
    finally:
        _refresh_running["value"] = False


@router.get("/status")
def status():
    snapshot = db.get_latest_snapshot()
    last_crawl = db.get_last_crawl()
    return {
        "predictions_enabled": settings.predictions_enabled,
        "grounded": bool(snapshot and snapshot.get("grounded")),
        "last_crawl_at": db.get_meta("last_crawl_at"),
        "last_prediction_at": db.get_meta("last_prediction_at"),
        "data_version": db.get_meta("data_version"),
        "refresh_running": _refresh_running["value"],
        "admin_required": bool(settings.admin_token),
        "last_crawl": last_crawl,
        "model": settings.claude_model,
        "monte_carlo_runs": settings.monte_carlo_runs,
        "teams": len(db.get_teams()),
        "matches": len(db.get_matches()),
        "has_snapshot": snapshot is not None,
    }


@router.get("/teams")
def teams():
    return [t.model_dump() for t in db.get_teams()]


@router.get("/teams/{team_id}")
def team(team_id: str):
    t = db.get_team(team_id)
    if not t:
        raise HTTPException(404, "team not found")
    dossier = db.get_dossier(team_id)
    return {"team": t.model_dump(), "dossier": dossier}


def _live_standings():
    teams = db.get_teams()
    matches = db.get_matches(stage="group")
    table: dict[str, dict] = {
        t.id: {
            "team_id": t.id, "team_name": t.name, "group": t.group,
            "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "gf": 0, "ga": 0, "gd": 0, "points": 0,
        }
        for t in teams
    }
    for m in matches:
        if m.status != "finished" or m.home_score is None or m.away_score is None:
            continue
        for tid, gf, ga in ((m.home_id, m.home_score, m.away_score),
                            (m.away_id, m.away_score, m.home_score)):
            row = table.get(tid)
            if not row:
                continue
            row["played"] += 1
            row["gf"] += gf
            row["ga"] += ga
            row["gd"] += gf - ga
            if gf > ga:
                row["won"] += 1
                row["points"] += 3
            elif gf == ga:
                row["drawn"] += 1
                row["points"] += 1
            else:
                row["lost"] += 1
    return table


@router.get("/groups")
def groups():
    standings = _live_standings()
    snapshot = db.get_latest_snapshot() or {}
    predictions = snapshot.get("group_predictions", {})
    out: dict[str, dict] = {}
    for row in standings.values():
        g = row["group"]
        if not g:
            continue
        out.setdefault(g, {"group": g, "standings": [], "predicted": predictions.get(g, [])})
        out[g]["standings"].append(row)
    for g in out.values():
        g["standings"].sort(key=lambda r: (r["points"], r["gd"], r["gf"]), reverse=True)
    return dict(sorted(out.items()))


@router.get("/matches")
def matches(stage: Optional[str] = Query(None), group: Optional[str] = Query(None)):
    ms = db.get_matches(stage=stage, group=group)
    preds = db.get_match_predictions()
    out = []
    for m in ms:
        d = m.model_dump()
        d["prediction"] = preds.get(m.id)
        out.append(d)
    return out


@router.get("/news")
def news():
    raw = db.get_meta("news_json")
    return json.loads(raw) if raw else []


@router.get("/bracket")
def bracket():
    snapshot = db.get_latest_snapshot()
    if not snapshot:
        raise HTTPException(404, "no prediction snapshot yet; trigger /api/refresh")
    return snapshot


@router.post("/whatif")
def whatif(body: dict = Body(...)):
    """Hypothetical bracket: caller supplies the 16 Round-of-32 ties as
    {"pairs": [[home_id, away_id], ... 16]} in official slot order (slot i =
    match 72+i). Returns the resolved knockout tree (same shape as
    /bracket -> bracket), recomputed with the current ratings. Free, LLM-less."""
    pairs = body.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != 16:
        raise HTTPException(422, "expected 'pairs': a list of 16 [home_id, away_id]")
    norm = [(p[0] or None, p[1] or None) for p in pairs]
    try:
        return whatif_bracket(norm)
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.post("/refresh")
def refresh(x_admin_token: str | None = Header(default=None)):
    # When an admin token is configured (production), require it. Without it
    # (local dev) refresh stays open.
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(403, "refresh is restricted to the site owner")
    with _refresh_lock:
        if _refresh_running["value"]:
            return {"started": False, "reason": "refresh already running"}
        _refresh_running["value"] = True
    threading.Thread(target=_do_refresh, daemon=True).start()
    return {"started": True}
