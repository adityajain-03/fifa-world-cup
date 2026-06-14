# 🏆 World Cup 2026 — Live Prediction Dashboard

An info web app that crawls public sources daily for 2026 FIFA World Cup data
and predicts the full bracket using a Claude multi-agent framework grounded by
Monte Carlo simulation. Predictions update as real results come in.

![stack](https://img.shields.io/badge/backend-FastAPI-009688) ![stack](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61dafb) ![model](https://img.shields.io/badge/predictions-Claude%20Opus%204.8-7c3aed)

## How predictions work

1. **Scout agents** (one Claude agent per team, run concurrently) read each
   team's FIFA-rank prior, recent results, and squad, and emit a numeric
   **strength rating** + a qualitative dossier.
2. An **Elo + Poisson** model turns rating gaps into per-match
   win/draw/loss probabilities and scorelines.
3. A **10,000-run Monte Carlo** simulation of the whole tournament produces each
   team's title and advancement odds; the bracket shown is the favourite path.
4. An **Analyst agent** writes the narrative briefing.

A team's title probability = the share of the 10,000 simulations it wins. See
[`CLAUDE.md`](./CLAUDE.md) for the full architecture.

> Runs without an API key in **ungrounded** mode (ratings from FIFA-rank priors).
> Set `ANTHROPIC_API_KEY` to enable Scout-agent analysis.

## Quick start

**Backend** (Python 3.12 via [uv](https://docs.astral.sh/uv/), port 8000):

```bash
cd backend
export ANTHROPIC_API_KEY=sk-ant-...        # optional
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend** (Node, port 5173):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The first run auto-populates data in the
background; use **Refresh now** to re-crawl + re-predict on demand. A scheduled
refresh runs daily at 06:00 local.

## Data sources

- **ESPN** public JSON API — fixtures, live scores, results, group field.
- **Wikipedia** — squad rosters (best-effort).

No data-provider API keys required.

## Layout

```
backend/   FastAPI app, crawlers, agents, Elo/Poisson + Monte Carlo model
frontend/  React + Vite dashboard (Overview / Groups / Bracket / Matches / Teams)
CLAUDE.md  architecture + multi-agent framework reference
```

## API

`GET /api/status` · `GET /api/groups` · `GET /api/bracket` ·
`GET /api/matches?stage=` · `GET /api/teams/{id}` · `POST /api/refresh`

## Notes

For an educational/demo project. Group letters are app-assigned (composition is
real); the knockout bracket is rating-seeded rather than the official slot map.
