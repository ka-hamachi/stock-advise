from __future__ import annotations

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import BASE_DIR, load_config
from src.pipeline import run_pipeline
from src.storage.database import Database

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(BASE_DIR / "data" / "stock_advise.log"),
        ],
    )

    config = load_config()
    db_path = BASE_DIR / config.get("storage", {}).get("db_path", "data/stock_advise.db")
    db = Database(db_path)

    schedule_cfg = config.get("schedule", {})
    cron_hours = schedule_cfg.get("cron_hours", "8,22")
    cron_minutes = schedule_cfg.get("cron_minutes", "0,0")

    # Build individual cron jobs for each time slot
    hours = [h.strip() for h in str(cron_hours).split(",")]
    minutes = [m.strip() for m in str(cron_minutes).split(",")]

    scheduler = BlockingScheduler()

    for i, (h, m) in enumerate(zip(hours, minutes)):
        scheduler.add_job(
            run_pipeline,
            trigger=CronTrigger(hour=int(h), minute=int(m)),
            args=[db, config],
            id=f"pipeline_{h}_{m}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
        logger.info("Scheduled pipeline at %s:%s", h, m)

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        scheduler.shutdown(wait=False)
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Run once immediately on start
    logger.info("Running initial pipeline...")
    run_pipeline(db, config)

    logger.info("Scheduler started. Next runs at %s",
                ", ".join(f"{h}:{m.zfill(2)}" for h, m in zip(hours, minutes)))
    scheduler.start()
