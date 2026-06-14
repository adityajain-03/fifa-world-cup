# CLAUDE.md — World Cup 2026 Prediction Dashboard

Context for Claude (and humans) working in this repo.

## What this is

A daily-updating web app that crawls public sources for 2026 FIFA World Cup
data and predicts the full bracket. The tournament is live (June 11 – July 19,
2026; 48 teams, 12 groups of 4 → Round of 32 → final). Predictions evolve as
real results come in.

- **Backend:** Python 3.12, FastAPI, SQLite, APScheduler, the Anthropic SDK. Managed by `uv`. Lives in `backend/`.
- **Frontend:** React + Vite (plain JS). Lives in `frontend/`.

## The prediction pipeline (grounded hybrid)

LLM agents set the *ratings*; deterministic math + simulation produce the
*probabilities*. Orchestrated in `backend/app/agents/orchestrator.py`.

1. **Scout agents** (`agents/scout.py`) — one per team, run concurrently (the
   multi-agent fan-out). Two steps: (a) crawl ESPN/BBC/FIFA headlines and
   summarise them into a news briefing with `claude-sonnet-4-6`; (b) an
   `claude-opus-4-8` structured-output call that turns the briefing + FIFA-rank
   prior + crawled results into a `ScoutDossier` (strength `rating` on an Elo
   scale, `attack_tilt`, `defense_tilt`, `form_rating`, `one_line_outlook`, plus
   the `briefing` text). Structured outputs via
   `client.messages.parse(output_format=ScoutDossier)`.
2. **Elo + Poisson** (`model/ratings.py`, deterministic) — converts a rating
   gap into per-match `P(home/draw/away)` + most-likely scoreline. Elo logistic
   for win expectancy → goal supremacy around a ~2.6-goal baseline → Poisson
   scoreline grid. Knockouts split the draw into a penalty edge for the
   stronger side.
3. **Monte Carlo** (`model/simulate.py`, deterministic) — simulates the whole
   tournament `MONTE_CARLO_RUNS` (default 10,000) times. Played matches use real
   results; the rest are sampled. Aggregates to per-team title / advancement
   odds. The displayed knockout bracket is the *favourite* path. No LLM calls
   in the loop (sub-second).
4. **Analyst agent** (`agents/analyst.py`) — one LLM call writing the narrative
   briefing from the computed odds.

A team's **win-the-cup probability = the fraction of the 10,000 simulations it
wins**. As results land, ratings shift → match probabilities shift → sims
re-run → odds move.

**Graceful degradation:** with no `ANTHROPIC_API_KEY`, Scouts are skipped,
ratings fall back to FIFA-rank priors, and the Elo/Poisson/Monte-Carlo bracket
still renders (`grounded=false`). Set the key and refresh to enable Scout
analysis.

## Update model (two paths)

- **Live results poll (automatic, cheap, LLM-free)** — `services/refresh.poll_results()`
  runs every `RESULTS_POLL_MINUTES` (default 5) via APScheduler (and once at
  startup). It fetches recent ESPN dates (short cache), and if a result changed,
  applies a **deterministic goal-difference-weighted Elo update** to the teams
  that played (`model/ratings.apply_match_elo`, layered on the news-anchored
  rating), then re-runs the match-prob model + 10k sim
  (`orchestrator.run_simulation_only()`) → updated **ratings, odds, and bracket**.
  No Wikipedia/news crawl, no Claude calls. Frontend auto-reloads when
  `last_prediction_at` changes.
- **Full refresh (manual, expensive)** — `POST /api/refresh` (owner-only, gated by
  `ADMIN_TOKEN`) runs `run_refresh()`: crawl ESPN+Wikipedia+news, re-scout teams
  (Claude news web search → ratings), simulate. This is the only path that spends
  API credit.

## Data flow (full refresh)

`services/refresh.run_refresh()` (manual button / `POST /api/refresh`):

1. **ESPN JSON API** (`crawlers/espn.py`) — authoritative for fixtures, results,
   live scores.
2. **Wikipedia** (`crawlers/wikipedia.py`) — `crawl_groups()` parses the article's
   12 per-group standings tables for the **official A–L groups** (composition +
   letters); `crawl_squads()` is best-effort rosters. If groups don't yield
   exactly 12, falls back to ESPN round-robin connected-components (composition
   real, letters strength-assigned).
3. **ESPN news** (`crawlers/news.py`) — headlines for the News panel.
4. **Seed** (`crawlers/seed.py`) — offline fallback field, used only if both
   sources are unreachable.
5. Predictions run (`agents/orchestrator.py`) → results stored → bracket snapshot.

**News grounding (no paid web_search):** `crawlers/news_sources.py` pulls recent
per-team headlines from **ESPN, BBC, and FIFA** via site-restricted Google News
RSS (clean XML — avoids fifa.com/ESPN's JS-rendered pages and needs no headless
browser). The Scout summarises those headlines into a briefing with a cheaper
model (`NEWS_MODEL`, default `claude-sonnet-4-6`), then Opus turns the briefing
+ FIFA-rank prior + results into the structured `rating`. Toggle with
`SCOUT_WEB_SEARCH` (name retained as the news on/off flag).

`data_version` = hash of finished results + rosters. Scout dossiers are cached
per team by `data_version`, so a daily refresh only re-scouts teams whose inputs
changed.

## Key files

- `backend/app/config.py` — settings & env vars (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `MONTE_CARLO_RUNS`, schedule, `REFRESH_ON_STARTUP`).
- `backend/app/db.py` — SQLite schema + helpers (teams, players, matches, match_predictions, team_dossiers, bracket_snapshots, crawl_runs, meta).
- `backend/app/models.py` — pydantic models (`ScoutDossier` is the Scout's structured-output schema).
- `backend/app/api/routes.py` — REST API (`/status /teams /groups /matches /bracket /refresh`).
- `backend/app/crawlers/aliases.py` — name normalisation, slugs, FIFA-rank priors, placeholder detection.
- `frontend/src/App.jsx` — dashboard shell (tabs: Overview/Groups/Bracket/Matches/Teams).

## Running it

```bash
# Backend (port 8000)
cd backend
export ANTHROPIC_API_KEY=sk-ant-...   # optional; omit for ungrounded mode
uv run uvicorn app.main:app --reload --port 8000

# Frontend (port 5173, proxies /api -> :8000)
cd frontend
npm install
npm run dev
```

First boot with an empty DB triggers a background refresh automatically
(`REFRESH_ON_STARTUP`). Or trigger one anytime with the dashboard's **Refresh
now** button / `curl -XPOST localhost:8000/api/refresh`.

## Conventions / gotchas

- **Anthropic usage** follows the `claude-api` skill: model `claude-opus-4-8`,
  `thinking={"type":"adaptive"}`, structured outputs via `messages.parse`,
  prompt caching on the system prompt, `stop_reason=="refusal"` handled. Don't
  downgrade the model or reintroduce `budget_tokens`.
- Team identity is a **slug** (`name_slug()` in `crawlers/aliases.py`). Always
  route new name sources through there so identities stay consistent.
- The knockout bracket follows the **official 2026 FIFA slot map**
  (`model/bracket_map.py`, verified against ESPN: R32 match 1 = "Group A 2nd v
  Group B 2nd", etc.). Group winners/runners-up resolve exactly from the
  standings; the 8 best thirds are assigned to their eligible third-slots. Group
  results already played are respected; real *knockout* results aren't yet pinned
  into the predicted bracket. The third-place slot assignment uses an
  eligibility-respecting matching rather than FIFA's exact lookup table.
- Crawlers cache raw responses under `backend/data/html_cache/` (TTL in config)
  and fall back to stale cache on network failure; runs are logged to
  `crawl_runs`.

## Known limitations / next steps

- Group letters come from Wikipedia's official group tables; the ESPN
  connected-components fallback uses strength-assigned letters.
- Wikipedia roster parsing is best-effort and may return 0 teams; the Scout
  works from rank + form + web_search regardless.
- Played knockout results aren't yet reconciled into the predicted bracket
  (which is rating-seeded).
