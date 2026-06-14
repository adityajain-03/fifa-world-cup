"""Scout agent: gather live news for a team, then turn it into a structured rating.

Two steps on purpose:
  1. crawl ESPN/BBC/FIFA headlines ourselves (news_sources) and have a cheap
     model (Sonnet) summarise them into a plain-text briefing, and
  2. a structured (no-tools) Opus call that returns a ScoutDossier (the rating).
Keeping tools out of the structured call guarantees valid JSON and a consistent
rating scale; crawling ourselves avoids the paid web_search tool.
"""
from __future__ import annotations

from ..config import settings
from ..crawlers.news_sources import team_news_blob
from ..models import Match, ScoutDossier, Team
from ..model.ratings import fifa_rank_to_rating
from .client import ClaudeClient
from .prompts import (
    NEWS_SYSTEM, SCOUT_SYSTEM, news_user_prompt, scout_user_prompt,
)


def _results_summary(team: Team, matches: list[Match]) -> str:
    lines = []
    for m in matches:
        if m.status != "finished":
            continue
        if team.id not in (m.home_id, m.away_id):
            continue
        if m.home_score is None or m.away_score is None:
            continue
        if team.id == m.home_id:
            lines.append(f"  {team.name} {m.home_score}-{m.away_score} {m.away_name} ({m.stage})")
        else:
            lines.append(f"  {m.home_name} {m.home_score}-{m.away_score} {team.name} ({m.stage})")
    return "\n".join(lines)


def _squad_summary(team: Team, limit: int = 12) -> str:
    if not team.players:
        return ""
    out = []
    for p in team.players[:limit]:
        bits = [p.name]
        if p.position:
            bits.append(f"({p.position})")
        if p.club:
            bits.append(f"- {p.club}")
        out.append("  " + " ".join(bits))
    return "\n".join(out)


def gather_news(client: ClaudeClient, team: Team) -> str:
    """Step 1: crawl ESPN/BBC/FIFA headlines, summarise into a briefing (Sonnet)."""
    if not settings.scout_web_search:
        return ""
    headlines = team_news_blob(team.name)
    if not headlines:
        return ""
    # Pure summarisation of provided text — cheap model, no thinking, no tools.
    return client.complete(
        NEWS_SYSTEM, news_user_prompt(team.name, headlines, settings.today),
        max_tokens=1500, model=settings.news_model, thinking={"type": "disabled"},
    )


def scout_team(client: ClaudeClient, team: Team, matches: list[Match]) -> ScoutDossier | None:
    prior = fifa_rank_to_rating(team.fifa_rank)
    briefing = gather_news(client, team)
    user = scout_user_prompt(
        team_name=team.name,
        fifa_rank=team.fifa_rank,
        group=team.group,
        results_summary=_results_summary(team, matches),
        squad_summary=_squad_summary(team),
        prior_rating=prior,
        today=settings.today,
        news_briefing=briefing,
    )
    # Structured call is numbers-only (small grammar, always compiles); no tools.
    dossier = client.parse(SCOUT_SYSTEM, user, ScoutDossier)
    if dossier is not None:
        dossier.briefing = briefing  # attach research text for display
    return dossier
