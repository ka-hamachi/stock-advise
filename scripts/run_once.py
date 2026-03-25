#!/usr/bin/env python3
"""Run the pipeline once and exit. Used by Windows Task Scheduler."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BASE_DIR, load_config
from src.pipeline import run_pipeline
from src.storage.database import Database


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(BASE_DIR / "data" / "stock_advise.log"),
        ],
    )
    logger = logging.getLogger(__name__)

    config = load_config()
    db_path = BASE_DIR / config.get("storage", {}).get("db_path", "data/stock_advise.db")
    db = Database(db_path)

    try:
        stats = run_pipeline(db, config)
        logger.info("Pipeline finished: %s", stats)
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
