"""Pydantic models shared between the crawler, prediction, and API layers."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

MatchStatus = Literal["scheduled", "live", "finished"]
Stage = Literal[
    "group",
    "round_of_32",
    "round_of_16",
    "quarter_final",
    "semi_final",
    "third_place",
    "final",
]


class Player(BaseModel):
    name: str
    position: str = ""
    club: str = ""
    caps: Optional[int] = None
    goals: Optional[int] = None


class Team(BaseModel):
    id: str  # slug, e.g. "argentina"
    name: str
    group: Optional[str] = None  # "A".."L"
    fifa_rank: Optional[int] = None
    flag_url: Optional[str] = None
    players: list[Player] = Field(default_factory=list)


class Match(BaseModel):
    id: str
    stage: Stage
    group: Optional[str] = None
    date: Optional[str] = None       # ISO date (YYYY-MM-DD)
    kickoff: Optional[str] = None     # full ISO datetime (UTC) from ESPN
    number: Optional[int] = None      # match number (1..104), chronological
    home_id: Optional[str] = None
    away_id: Optional[str] = None
    home_name: Optional[str] = None
    away_name: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: MatchStatus = "scheduled"


class MatchPrediction(BaseModel):
    match_id: str
    p_home: float
    p_draw: float
    p_away: float
    most_likely_score: str
    expected_home_goals: float
    expected_away_goals: float


# --- Scout agent structured output ---


class ScoutDossier(BaseModel):
    """Scout output.

    The numeric fields come from a small structured-output call (so the grammar
    always compiles and parsing never fails). The qualitative detail — current
    form, 4-year trajectory, projected XI, injuries — is carried in `briefing`
    (the plain-text research the Scout gathered via web search) and attached
    after parsing; it is for display, not part of the structured schema.
    """

    rating: float = Field(description="Overall strength rating, ~1300-2100 Elo scale.")
    attack_tilt: float = Field(
        0.0, description="-1 (defensive) .. +1 (attacking) skew applied to expected goals."
    )
    defense_tilt: float = Field(
        0.0, description="-1 (leaky) .. +1 (solid) defensive adjustment."
    )
    form_rating: float = Field(0.0, description="-1 (poor form) .. +1 (red hot).")
    one_line_outlook: str = Field("", description="One-sentence outlook for this team.")
    # Attached after the structured call (NOT part of the LLM grammar):
    briefing: str = ""


class TeamOdds(BaseModel):
    team_id: str
    team_name: str
    rating: float
    win_title: float
    reach_final: float
    reach_semi: float
    reach_quarter: float
    reach_r16: float
    reach_r32: float
    win_group: float
    advance_group: float


class BracketSnapshot(BaseModel):
    created_at: str
    data_version: str
    grounded: bool
    odds: list[TeamOdds]
    bracket: dict  # modal knockout path, slot -> team
    group_predictions: dict  # group -> ordered list of {team_id, expected_points, ...}
    ticket_prices: list[dict] = []  # R16+ resale price estimates per match
    analyst_narrative: str = ""
