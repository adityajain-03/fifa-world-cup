"""Analyst agent: turns the computed odds + bracket into a human briefing."""
from __future__ import annotations

from .client import ClaudeClient
from .prompts import ANALYST_SYSTEM, analyst_user_prompt


def write_narrative(client: ClaudeClient, odds: dict, bracket: dict) -> str:
    if not client.available:
        return ""
    top = sorted(odds.values(), key=lambda o: o["win_title"], reverse=True)[:8]
    odds_summary = "\n".join(
        f"  {o['team_name']}: {o['win_title'] * 100:.1f}% title, "
        f"{o['reach_final'] * 100:.0f}% final (rating {o['rating']:.0f})"
        for o in top
    )
    champ = bracket.get("champion", {}) if isinstance(bracket, dict) else {}
    final = bracket.get("final", []) if isinstance(bracket, dict) else []
    bits = [f"  Predicted champion: {champ.get('team', 'TBD')}"]
    for tie in final:
        bits.append(f"  Final: {tie['home']} vs {tie['away']} -> {tie['winner']}")
    return client.complete(ANALYST_SYSTEM, analyst_user_prompt(odds_summary, "\n".join(bits)))
