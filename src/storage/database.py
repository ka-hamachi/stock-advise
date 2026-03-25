from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Alert, RawItem


class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                url TEXT,
                published_at TIMESTAMP,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_hash TEXT UNIQUE NOT NULL,
                processed BOOLEAN DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_raw_processed ON raw_items(processed);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                alert_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                urgency TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                source_urls TEXT,
                raw_item_ids TEXT,
                alert_hash TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_to_slack BOOLEAN DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                items_collected INTEGER DEFAULT 0,
                alerts_generated INTEGER DEFAULT 0,
                alerts_sent INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def insert_raw_item(self, item: RawItem) -> bool:
        try:
            self.conn.execute(
                """INSERT INTO raw_items (source, title, content, url, published_at, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (item.source, item.title, item.content, item.url,
                 item.published_at.isoformat() if item.published_at else None,
                 item.content_hash),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_unprocessed_items(self, limit: int = 50) -> list[RawItem]:
        rows = self.conn.execute(
            "SELECT * FROM raw_items WHERE processed = 0 ORDER BY collected_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_raw_item(r) for r in rows]

    def mark_processed(self, ids: list[int]):
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(
            f"UPDATE raw_items SET processed = 1 WHERE id IN ({placeholders})", ids
        )
        self.conn.commit()

    def insert_alert(self, alert: Alert) -> bool:
        try:
            self.conn.execute(
                """INSERT INTO alerts
                   (ticker, alert_type, confidence, urgency, reasoning,
                    source_urls, raw_item_ids, alert_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (alert.ticker, alert.alert_type, alert.confidence, alert.urgency,
                 alert.reasoning, json.dumps(alert.source_urls),
                 json.dumps(alert.raw_item_ids), alert.alert_hash),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def alert_exists(self, alert_hash: str, window_hours: int = 24) -> bool:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
        row = self.conn.execute(
            "SELECT 1 FROM alerts WHERE alert_hash = ? AND created_at > ?",
            (alert_hash, cutoff),
        ).fetchone()
        return row is not None

    def log_run(self, started_at: datetime, items: int, alerts_gen: int, alerts_sent: int):
        self.conn.execute(
            """INSERT INTO collection_runs
               (started_at, completed_at, items_collected, alerts_generated, alerts_sent)
               VALUES (?, ?, ?, ?, ?)""",
            (started_at.isoformat(), datetime.now(timezone.utc).isoformat(),
             items, alerts_gen, alerts_sent),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    @staticmethod
    def _row_to_raw_item(row: sqlite3.Row) -> RawItem:
        return RawItem(
            id=row["id"],
            source=row["source"],
            title=row["title"],
            content=row["content"],
            url=row["url"],
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
            collected_at=datetime.fromisoformat(row["collected_at"]) if row["collected_at"] else None,
            content_hash=row["content_hash"],
            processed=bool(row["processed"]),
        )
