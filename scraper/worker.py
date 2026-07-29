"""Scheduled scraper worker — the Railway worker service entry point.

Launched by `python -m scraper.worker` (see railway.worker.toml). Every
`settings.SCRAPE_INTERVAL_HOURS` it runs a full scrape across the configured
games (`settings.SCRAPE_GAMES`) and then dispatches alerts. A run that fails is
logged and swallowed so the worker process keeps living; Railway's restart
policy handles a hard crash.
"""
from __future__ import annotations

import io
import logging
import sys
import datetime as dt

from apscheduler.schedulers.blocking import BlockingScheduler

from api.config import settings
from scraper.run import GAME_GROUPS, take_snapshot
from scraper.alerting import run_alerting

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scraper.worker")


def _resolve_games():
    """Map settings.SCRAPE_GAMES ('all'|'optcg'|'pokemon') to DB game ids."""
    scope = (settings.SCRAPE_GAMES or "all").strip().lower()
    if scope not in GAME_GROUPS:
        logger.warning("Unknown SCRAPE_GAMES=%r; falling back to 'all'.", scope)
        scope = "all"
    return scope, GAME_GROUPS[scope]


def run_cycle() -> None:
    """One full scrape + alert cycle. Never raises (logs and returns)."""
    scope, games = _resolve_games()
    started = dt.datetime.now()
    logger.info("=== Scrape cycle start (games=%s) ===", scope)

    # --- scrape -------------------------------------------------------------
    try:
        take_snapshot(games)
        logger.info("Scrape finished in %s", dt.datetime.now() - started)
    except Exception:
        logger.exception("Scrape step FAILED — skipping alerting this cycle.")
        return

    # --- alerting -----------------------------------------------------------
    try:
        summary = run_alerting()
        logger.info("Alerting finished: %s", summary)
    except Exception:
        logger.exception("Alerting step FAILED.")

    logger.info("=== Scrape cycle done in %s ===", dt.datetime.now() - started)


def main() -> None:
    # Force UTF-8 stdout/stderr on Windows so logs with €/accents don't blow up.
    # Done here (not at import) so the module stays import-safe under tests/tools.
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    interval = max(1, int(settings.SCRAPE_INTERVAL_HOURS or 6))
    logger.info(
        "Worker starting: interval=%dh, games=%s, db=%s",
        interval, settings.SCRAPE_GAMES, settings.DATABASE_URL[:24],
    )

    # Run once immediately so deploys produce data without waiting a full cycle.
    run_cycle()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_cycle,
        trigger="interval",
        hours=interval,
        next_run_time=dt.datetime.now() + dt.timedelta(hours=interval),
        id="scrape_cycle",
        max_instances=1,        # never overlap two cycles
        coalesce=True,          # if we fell behind, run once not N times
        misfire_grace_time=3600,
    )
    logger.info("Scheduler armed; next run in %dh.", interval)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker stopping.")


if __name__ == "__main__":
    main()
