"""FastAPI entrypoint: wires the API, CORS, the DB, and the daily scheduler."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import BASE_DIR, settings
from .db import get_last_crawl, init_db
from .services.refresh import poll_results, run_refresh

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("fifa")

scheduler = AsyncIOScheduler()


def _scheduled_full_refresh() -> None:
    log.info("Scheduled full refresh starting")
    try:
        run_refresh()
    except Exception:  # noqa: BLE001 - scheduler must never crash
        log.exception("Scheduled refresh failed")


def _scheduled_results_poll() -> None:
    try:
        poll_results()
    except Exception:  # noqa: BLE001
        log.exception("Results poll failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Frequent, LLM-free live poll: updates bracket/odds when results change.
    # (News/ratings stay manual via the Refresh button — see services/refresh.)
    scheduler.add_job(
        _scheduled_results_poll,
        IntervalTrigger(minutes=settings.results_poll_minutes),
        id="results_poll",
        replace_existing=True,
        next_run_time=None,
    )
    scheduler.start()
    log.info("Scheduler started; live results poll every %d min", settings.results_poll_minutes)
    if settings.refresh_on_startup and get_last_crawl() is None:
        # First boot with an empty DB: populate fully in the background.
        scheduler.add_job(_scheduled_full_refresh, id="startup_refresh", replace_existing=True)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="FIFA World Cup 2026 Predictions", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


# Serve the built React app (single-service deploy). In dev, when no build
# exists, fall back to a small JSON root so the API is still browsable.
_DIST = BASE_DIR / "app" / "static"  # frontend build is copied here at deploy time
if _DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
    log.info("Serving frontend build from %s", _DIST)
else:
    @app.get("/")
    def root():
        return {"service": "fifa-wc-2026", "docs": "/docs", "api": "/api"}
