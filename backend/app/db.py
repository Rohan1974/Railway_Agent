"""SQLite helpers. One file holds railway data, bookings and telemetry."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trains (
    number TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
    days_of_run TEXT NOT NULL,          -- 7 chars Mon..Sun, '1' = runs
    classes TEXT NOT NULL               -- comma separated, e.g. 'SL,3A,2A'
);
CREATE TABLE IF NOT EXISTS train_stops (
    train_number TEXT NOT NULL, seq INTEGER NOT NULL, station_code TEXT NOT NULL,
    arr TEXT, dep TEXT, day_offset INTEGER NOT NULL, km INTEGER NOT NULL,
    PRIMARY KEY (train_number, seq)
);
CREATE TABLE IF NOT EXISTS inventory (
    train_number TEXT NOT NULL, journey_date TEXT NOT NULL, travel_class TEXT NOT NULL,
    seats_left INTEGER NOT NULL, wl_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (train_number, journey_date, travel_class)
);
CREATE TABLE IF NOT EXISTS bookings (
    pnr TEXT PRIMARY KEY, train_number TEXT NOT NULL, journey_date TEXT NOT NULL,
    from_code TEXT NOT NULL, to_code TEXT NOT NULL, travel_class TEXT NOT NULL,
    quota TEXT NOT NULL, total_fare REAL NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS passengers (
    pnr TEXT NOT NULL, seq INTEGER NOT NULL, name TEXT NOT NULL, age INTEGER NOT NULL,
    gender TEXT NOT NULL, berth_pref TEXT, status TEXT NOT NULL,
    PRIMARY KEY (pnr, seq)
);

-- Telemetry: one row per model call (Claude or Jev)
CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, run_id TEXT, conversation_id TEXT, turn_id TEXT,
    mode TEXT NOT NULL, step TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0, cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    thinking_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL, cost_usd REAL NOT NULL, ok INTEGER NOT NULL, error TEXT
);
-- Telemetry: one row per tool execution
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, run_id TEXT, conversation_id TEXT, turn_id TEXT, mode TEXT NOT NULL,
    tool TEXT NOT NULL, latency_ms REAL NOT NULL, ok INTEGER NOT NULL, args TEXT
);
-- Benchmark runs: one row per eval run, so every number can be traced to its settings
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, ts TEXT NOT NULL, bench TEXT NOT NULL, modes TEXT NOT NULL,
    model TEXT NOT NULL, effort TEXT NOT NULL, repeats INTEGER NOT NULL, items INTEGER NOT NULL,
    dataset_sha TEXT NOT NULL, git_commit TEXT, fake INTEGER NOT NULL, status TEXT NOT NULL,
    summary_json TEXT
);
-- Telemetry: one row per user turn (end-to-end)
CREATE TABLE IF NOT EXISTS turns (
    turn_id TEXT PRIMARY KEY, ts TEXT NOT NULL, run_id TEXT, conversation_id TEXT,
    mode TEXT NOT NULL, user_text TEXT, reply_text TEXT,
    latency_ms REAL NOT NULL, cost_usd REAL NOT NULL, llm_calls INTEGER NOT NULL,
    decision_calls INTEGER NOT NULL DEFAULT 0, tool_calls INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first release. init_schema adds them to older databases.
MIGRATIONS = {"tool_calls": {"args": "TEXT"}}


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, typ in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    conn.commit()


@contextmanager
def tx(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
