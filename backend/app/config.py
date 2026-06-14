"""Application settings, read from environment (and an optional .env file)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Access control ---
    # If set, POST /api/refresh requires this token (header X-Admin-Token).
    # Leave unset for local dev (refresh open). Set it in production so only
    # you can trigger the expensive refresh.
    admin_token: str | None = None

    # --- Anthropic ---
    anthropic_api_key: str | None = None
    # The model used by every agent. See the claude-api skill: opus-4-8 is current.
    claude_model: str = "claude-opus-4-8"
    # Cheaper model for summarising crawled news headlines into the briefing.
    news_model: str = "claude-sonnet-4-6"

    # --- Storage / caching ---
    db_path: Path = BASE_DIR / "data" / "fifa.db"
    # Pre-built grounded DB baked into the image; copied to db_path on first boot
    # so a fresh container/volume starts populated (no startup API cost).
    seed_db_path: Path = BASE_DIR / "seed" / "fifa.db"
    html_cache_dir: Path = BASE_DIR / "data" / "html_cache"
    # How long a cached HTML page is considered fresh, in hours.
    html_cache_ttl_hours: float = 6.0

    # --- Simulation ---
    monte_carlo_runs: int = 10_000

    # --- Scheduler ---
    daily_refresh_hour: int = 6  # local time
    daily_refresh_minute: int = 0
    # Run a refresh once shortly after startup if the DB is empty.
    refresh_on_startup: bool = True
    # How often to poll ESPN for live results and re-simulate the bracket/odds.
    # Cheap + LLM-free: only the deterministic model runs, using cached ratings.
    results_poll_minutes: int = 5

    # --- Concurrency for Scout agents ---
    scout_concurrency: int = 4
    # Let Scout agents use Claude's web_search tool to ground on live news/injuries.
    scout_web_search: bool = True
    # Today's date, surfaced to the Scout so web searches are timely.
    today: str = "2026-06-13"

    @property
    def predictions_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
