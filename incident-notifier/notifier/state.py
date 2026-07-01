"""Persistenter Lebenszyklus pro Incident fuer die Eskalation.

Pro Incident merkt sich der Dienst:
  - wann zuerst gesehen
  - welche Eskalationsstufe zuletzt gesendet wurde (stage) und wann (stage_sent_at)
  - den Zustand: active | acknowledged | resolved
  - Titel/Quelle (fuer eine spaetere Entwarnung, wenn der Vorfall verschwindet)

Nutzt SQLite (stdlib), damit ein Neustart keine Stufe verliert oder doppelt sendet.
"""
import sqlite3
import time
import os


class StateStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                key           TEXT PRIMARY KEY,
                first_seen    REAL NOT NULL,
                stage         INTEGER NOT NULL,
                stage_sent_at REAL NOT NULL,
                state         TEXT NOT NULL,       -- active | acknowledged | resolved
                severity      TEXT,
                title         TEXT,
                source        TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS send_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at       REAL NOT NULL,
                incident_id   TEXT NOT NULL,
                incident_title TEXT,
                severity      TEXT,
                channel       TEXT NOT NULL,
                kind          TEXT NOT NULL DEFAULT 'alert'
            )
            """
        )
        self.conn.commit()

    def get(self, key: str):
        row = self.conn.execute(
            "SELECT * FROM incidents WHERE key = ?", (key,)
        ).fetchone()
        return dict(row) if row else None

    def start(self, inc, stage: int = 0):
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO incidents (key, first_seen, stage, stage_sent_at, state, severity, title, source)
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                stage=excluded.stage, stage_sent_at=excluded.stage_sent_at,
                state='active', severity=excluded.severity,
                title=excluded.title, source=excluded.source
            """,
            (inc.id, now, stage, now, inc.severity, inc.title, inc.source),
        )
        self.conn.commit()

    def advance(self, key: str, stage: int):
        self.conn.execute(
            "UPDATE incidents SET stage=?, stage_sent_at=? WHERE key=?",
            (stage, time.time(), key),
        )
        self.conn.commit()

    def set_state(self, key: str, state: str):
        self.conn.execute(
            "UPDATE incidents SET state=? WHERE key=?", (state, key)
        )
        self.conn.commit()

    def active(self):
        rows = self.conn.execute(
            "SELECT * FROM incidents WHERE state='active'"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()

    def log_send(self, incident_id: str, channel: str, kind: str = "alert", title: str = "", severity: str = ""):
        self.conn.execute(
            "INSERT INTO send_history (sent_at, incident_id, incident_title, severity, channel, kind) VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), incident_id, title, severity, channel, kind),
        )
        self.conn.commit()

    def get_history(self, limit: int = 100):
        rows = self.conn.execute(
            "SELECT * FROM send_history ORDER BY sent_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
