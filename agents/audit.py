"""SQLite audit helpers for explainability, safety, faults, and human review."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "results.db")


def _connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialise_audit_tables() -> None:
    with _connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS decision_trace (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cycle INTEGER,
                agent TEXT NOT NULL,
                input_json TEXT NOT NULL,
                reasoning TEXT,
                recommendation REAL,
                confidence REAL,
                effect_on_final TEXT,
                final_decision REAL
            );
            CREATE TABLE IF NOT EXISTS safety_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cycle INTEGER,
                event_type TEXT NOT NULL,
                requested_temp REAL,
                applied_temp REAL,
                source TEXT,
                details_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sensor_anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cycle INTEGER,
                code TEXT NOT NULL,
                message TEXT NOT NULL,
                state_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS facility_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                requested_temp REAL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_at TEXT,
                outcome_json TEXT
            );
        """)


def log_trace(cycle: int, agent: str, inputs: dict, reasoning: str, recommendation: float | None,
              confidence: float | None, effect_on_final: str, final_decision: float | None) -> None:
    initialise_audit_tables()
    with _connection() as conn:
        conn.execute("""INSERT INTO decision_trace
            (timestamp, cycle, agent, input_json, reasoning, recommendation, confidence, effect_on_final, final_decision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            datetime.now().isoformat(), cycle, agent, json.dumps(inputs, default=str), reasoning,
            recommendation, confidence, effect_on_final, final_decision,
        ))


def log_safety_event(cycle: int, event_type: str, decision: dict) -> None:
    initialise_audit_tables()
    with _connection() as conn:
        conn.execute("""INSERT INTO safety_events
            (timestamp, cycle, event_type, requested_temp, applied_temp, source, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (
            datetime.now().isoformat(), cycle, event_type, decision.get("requested_temp"),
            decision.get("applied_temp"), decision.get("source"), json.dumps(decision, default=str),
        ))


def log_anomalies(cycle: int, anomalies: list[dict], state: dict) -> None:
    initialise_audit_tables()
    with _connection() as conn:
        conn.executemany("""INSERT INTO sensor_anomalies
            (timestamp, cycle, code, message, state_json) VALUES (?, ?, ?, ?, ?)""", [
                (datetime.now().isoformat(), cycle, item["code"], item["message"], json.dumps(state, default=str))
                for item in anomalies
            ])


def queue_facility_override(action: str, requested_temp: float | None, reason: str) -> int:
    initialise_audit_tables()
    with _connection() as conn:
        cursor = conn.execute("""INSERT INTO facility_overrides
            (timestamp, action, requested_temp, reason, status) VALUES (?, ?, ?, ?, 'pending')""",
            (datetime.now().isoformat(), action, requested_temp, reason))
        return int(cursor.lastrowid)


def get_pending_override() -> dict | None:
    initialise_audit_tables()
    with _connection() as conn:
        row = conn.execute("""SELECT * FROM facility_overrides
            WHERE status = 'pending' ORDER BY id DESC LIMIT 1""").fetchone()
        return dict(row) if row else None


def close_override(override_id: int, outcome: dict) -> None:
    with _connection() as conn:
        conn.execute("""UPDATE facility_overrides SET status = ?, reviewed_at = ?, outcome_json = ? WHERE id = ?""", (
            "applied" if outcome.get("approved") else "rejected", datetime.now().isoformat(),
            json.dumps(outcome, default=str), override_id,
        ))


def recent_energy_j(limit: int = 12) -> list[float]:
    if not os.path.exists(DB_PATH):
        return []
    try:
        with _connection() as conn:
            rows = conn.execute("SELECT energy_kw FROM ai_results WHERE energy_kw IS NOT NULL ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [float(row[0]) for row in rows]
    except sqlite3.Error:
        return []
