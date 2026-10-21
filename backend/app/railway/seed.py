"""Create and seed the SQLite database: `python -m app.railway.seed` (run from backend/)."""
import sqlite3

from ..db import connect, init_schema, tx
from .seed_data import STATIONS, TRAINS


def seed(conn: sqlite3.Connection, reset: bool = False) -> None:
    init_schema(conn)
    with tx(conn):
        if reset:
            for t in ("passengers", "bookings", "inventory", "train_stops", "trains", "stations"):
                conn.execute(f"DELETE FROM {t}")
        conn.executemany("INSERT OR REPLACE INTO stations VALUES (?,?,?,?)", STATIONS)
        for number, name, ttype, days, classes, stops in TRAINS:
            conn.execute("INSERT OR REPLACE INTO trains VALUES (?,?,?,?,?)", (number, name, ttype, days, classes))
            conn.execute("DELETE FROM train_stops WHERE train_number = ?", (number,))
            conn.executemany(
                "INSERT INTO train_stops VALUES (?,?,?,?,?,?,?)",
                [(number, i, code, arr, dep, day, km) for i, (code, arr, dep, day, km) in enumerate(stops)],
            )


if __name__ == "__main__":
    c = connect()
    seed(c, reset=True)
    n_st = c.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    n_tr = c.execute("SELECT COUNT(*) FROM trains").fetchone()[0]
    print(f"Seeded {n_st} stations and {n_tr} trains.")
