"""SQLite storage layer. Plain sqlite3 with small typed helpers."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Iterator, Optional

from .config import settings
from .models import Match, Player, Team

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    "group" TEXT,
    fifa_rank INTEGER,
    flag_url TEXT
);
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    club TEXT,
    caps INTEGER,
    goals INTEGER,
    UNIQUE(team_id, name)
);
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    "group" TEXT,
    date TEXT,
    home_id TEXT,
    away_id TEXT,
    home_name TEXT,
    away_name TEXT,
    home_score INTEGER,
    away_score INTEGER,
    status TEXT NOT NULL DEFAULT 'scheduled'
);
CREATE TABLE IF NOT EXISTS match_predictions (
    match_id TEXT PRIMARY KEY,
    p_home REAL, p_draw REAL, p_away REAL,
    most_likely_score TEXT,
    expected_home_goals REAL,
    expected_away_goals REAL,
    data_version TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS team_dossiers (
    team_id TEXT PRIMARY KEY,
    rating REAL,
    attack_tilt REAL,
    defense_tilt REAL,
    payload_json TEXT,
    data_version TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS bracket_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    data_version TEXT,
    grounded INTEGER,
    payload_json TEXT
);
CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    # On a fresh deploy (no DB yet), seed from the baked grounded snapshot so the
    # dashboard boots populated without running the expensive pipeline.
    if not settings.db_path.exists() and settings.seed_db_path.exists():
        import shutil

        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(settings.seed_db_path, settings.db_path)
    with connect() as conn:
        conn.executescript(SCHEMA)


# --- meta key/value -------------------------------------------------------

def set_meta(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_meta(key: str) -> Optional[str]:
    with connect() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


# --- teams / players ------------------------------------------------------

def upsert_teams(teams: Iterable[Team]) -> None:
    with connect() as conn:
        for t in teams:
            conn.execute(
                'INSERT INTO teams(id, name, "group", fifa_rank, flag_url) '
                "VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                'name=excluded.name, "group"=excluded."group", '
                "fifa_rank=COALESCE(excluded.fifa_rank, teams.fifa_rank), "
                "flag_url=COALESCE(excluded.flag_url, teams.flag_url)",
                (t.id, t.name, t.group, t.fifa_rank, t.flag_url),
            )
            for p in t.players:
                conn.execute(
                    "INSERT INTO players(team_id, name, position, club, caps, goals) "
                    "VALUES(?,?,?,?,?,?) ON CONFLICT(team_id, name) DO UPDATE SET "
                    "position=excluded.position, club=excluded.club, "
                    "caps=excluded.caps, goals=excluded.goals",
                    (t.id, p.name, p.position, p.club, p.caps, p.goals),
                )


def get_teams() -> list[Team]:
    with connect() as conn:
        rows = conn.execute('SELECT * FROM teams ORDER BY "group", name').fetchall()
        teams: list[Team] = []
        for r in rows:
            players = conn.execute(
                "SELECT * FROM players WHERE team_id=? ORDER BY name", (r["id"],)
            ).fetchall()
            teams.append(
                Team(
                    id=r["id"],
                    name=r["name"],
                    group=r["group"],
                    fifa_rank=r["fifa_rank"],
                    flag_url=r["flag_url"],
                    players=[
                        Player(
                            name=p["name"],
                            position=p["position"] or "",
                            club=p["club"] or "",
                            caps=p["caps"],
                            goals=p["goals"],
                        )
                        for p in players
                    ],
                )
            )
        return teams


def get_team(team_id: str) -> Optional[Team]:
    for t in get_teams():
        if t.id == team_id:
            return t
    return None


# --- matches --------------------------------------------------------------

def upsert_matches(matches: Iterable[Match]) -> None:
    with connect() as conn:
        for m in matches:
            conn.execute(
                'INSERT INTO matches(id, stage, "group", date, home_id, away_id, '
                "home_name, away_name, home_score, away_score, status) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                'stage=excluded.stage, "group"=excluded."group", date=excluded.date, '
                "home_id=COALESCE(excluded.home_id, matches.home_id), "
                "away_id=COALESCE(excluded.away_id, matches.away_id), "
                "home_name=COALESCE(excluded.home_name, matches.home_name), "
                "away_name=COALESCE(excluded.away_name, matches.away_name), "
                "home_score=excluded.home_score, away_score=excluded.away_score, "
                "status=excluded.status",
                (
                    m.id, m.stage, m.group, m.date, m.home_id, m.away_id,
                    m.home_name, m.away_name, m.home_score, m.away_score, m.status,
                ),
            )


def get_matches(stage: Optional[str] = None, group: Optional[str] = None) -> list[Match]:
    q = "SELECT * FROM matches"
    clauses, params = [], []
    if stage:
        clauses.append("stage=?")
        params.append(stage)
    if group:
        clauses.append('"group"=?')
        params.append(group)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY date, id"
    with connect() as conn:
        rows = conn.execute(q, params).fetchall()
        return [Match(**dict(r)) for r in rows]


# --- predictions / dossiers / snapshots -----------------------------------

def store_match_predictions(preds, data_version: str) -> None:
    with connect() as conn:
        for p in preds:
            conn.execute(
                "INSERT INTO match_predictions(match_id, p_home, p_draw, p_away, "
                "most_likely_score, expected_home_goals, expected_away_goals, "
                "data_version, created_at) VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(match_id) DO UPDATE SET p_home=excluded.p_home, "
                "p_draw=excluded.p_draw, p_away=excluded.p_away, "
                "most_likely_score=excluded.most_likely_score, "
                "expected_home_goals=excluded.expected_home_goals, "
                "expected_away_goals=excluded.expected_away_goals, "
                "data_version=excluded.data_version, created_at=excluded.created_at",
                (
                    p.match_id, p.p_home, p.p_draw, p.p_away, p.most_likely_score,
                    p.expected_home_goals, p.expected_away_goals, data_version, now_iso(),
                ),
            )


def get_match_predictions() -> dict[str, dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM match_predictions").fetchall()
        return {r["match_id"]: dict(r) for r in rows}


def store_dossier(team_id: str, dossier, data_version: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO team_dossiers(team_id, rating, attack_tilt, defense_tilt, "
            "payload_json, data_version, created_at) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(team_id) DO UPDATE SET rating=excluded.rating, "
            "attack_tilt=excluded.attack_tilt, defense_tilt=excluded.defense_tilt, "
            "payload_json=excluded.payload_json, data_version=excluded.data_version, "
            "created_at=excluded.created_at",
            (
                team_id, dossier.rating, dossier.attack_tilt, dossier.defense_tilt,
                dossier.model_dump_json(), data_version, now_iso(),
            ),
        )


def get_dossiers() -> dict[str, dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM team_dossiers").fetchall()
        return {r["team_id"]: dict(r) for r in rows}


def get_dossier(team_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM team_dossiers WHERE team_id=?", (team_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d["payload_json"]) if d["payload_json"] else {}
        return d


def store_snapshot(snapshot) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO bracket_snapshots(created_at, data_version, grounded, payload_json) "
            "VALUES(?,?,?,?)",
            (snapshot.created_at, snapshot.data_version, int(snapshot.grounded),
             snapshot.model_dump_json()),
        )


def get_latest_snapshot() -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM bracket_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return json.loads(row["payload_json"]) if row else None


# --- crawl run logging ----------------------------------------------------

def start_crawl_run(source: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO crawl_runs(source, started_at, status) VALUES(?,?,?)",
            (source, now_iso(), "running"),
        )
        return cur.lastrowid


def finish_crawl_run(run_id: int, status: str, notes: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE crawl_runs SET finished_at=?, status=?, notes=? WHERE id=?",
            (now_iso(), status, notes, run_id),
        )


def get_last_crawl() -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
