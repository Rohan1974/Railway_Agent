"""Mock railway service. Pure Python + SQLite, deterministic, no network.

Both agent modes call exactly these functions, so tool latency is identical across modes.
"""
from __future__ import annotations

import hashlib
import os
import random
import sqlite3
from datetime import date, datetime, timedelta

from ..db import tx
from .seed_data import CLASS_INFO, MIN_FARE, PREMIUM_TYPES, QUOTAS

ADVANCE_BOOKING_DAYS = 60
MAX_PASSENGERS = {"GN": 6, "LD": 6, "SS": 6, "TQ": 4}
COACH_PREFIX = {"SL": "S", "3A": "B", "2A": "A", "1A": "H", "CC": "C", "EC": "E"}
CANCEL_CHARGE = {"SL": 120, "3A": 180, "2A": 200, "1A": 240, "CC": 180, "EC": 240}
ALIASES = {"bombay": "mumbai", "bangalore": "bengaluru", "poona": "pune", "panjim": "panaji",
           "new delhi": "delhi", "amravati": "amravati", "nasik": "nashik"}


class RailwayError(ValueError):
    """User-facing validation error (returned to the model as a tool error)."""


def today() -> date:
    """`TODAY=YYYY-MM-DD` env var pins the date, so benchmark runs are reproducible."""
    pinned = os.getenv("TODAY")
    return date.fromisoformat(pinned) if pinned else date.today()


class RailwayService:
    def __init__(self, conn: sqlite3.Connection, rng: random.Random | None = None):
        self.conn = conn
        self.rng = rng or random.Random()

    # ---------- helpers ----------
    def resolve_station(self, query: str) -> list[str]:
        q = (query or "").strip()
        if not q:
            raise RailwayError("Station is empty.")
        row = self.conn.execute("SELECT code FROM stations WHERE code = ?", (q.upper(),)).fetchone()
        if row:
            return [row["code"]]
        ql = ALIASES.get(q.lower(), q.lower())
        rows = self.conn.execute(
            "SELECT code FROM stations WHERE lower(name) = ? OR lower(city) = ? OR lower(state) = ?",
            (ql, ql, ql)).fetchall()
        if not rows:
            rows = self.conn.execute(
                "SELECT code FROM stations WHERE lower(name) LIKE ? OR lower(city) LIKE ?",
                (f"%{ql}%", f"%{ql}%")).fetchall()
        if not rows:
            raise RailwayError(f"Unknown station '{query}'.")
        return [r["code"] for r in rows]

    def _station_name(self, code: str) -> str:
        return self.conn.execute("SELECT name FROM stations WHERE code = ?", (code,)).fetchone()["name"]

    @staticmethod
    def _parse_date(value: str) -> date:
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            raise RailwayError(f"Date '{value}' must be in YYYY-MM-DD format.")

    def _check_booking_window(self, d: date) -> None:
        t = today()
        if d < t:
            raise RailwayError(f"{d} is in the past (today is {t}).")
        if d > t + timedelta(days=ADVANCE_BOOKING_DAYS):
            raise RailwayError(f"Booking opens only {ADVANCE_BOOKING_DAYS} days in advance.")

    def _train(self, number: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM trains WHERE number = ?", (str(number),)).fetchone()
        if not row:
            raise RailwayError(f"Train {number} not found.")
        return row

    def _stops(self, number: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM train_stops WHERE train_number = ? ORDER BY seq", (number,)).fetchall()

    def _segment(self, number: str, from_q: str, to_q: str):
        """Return (from_stop, to_stop) for a train, or raise."""
        from_codes, to_codes = set(self.resolve_station(from_q)), set(self.resolve_station(to_q))
        stops = self._stops(number)
        for i, a in enumerate(stops):
            if a["station_code"] in from_codes:
                for b in stops[i + 1:]:
                    if b["station_code"] in to_codes:
                        return a, b
        raise RailwayError(f"Train {number} does not run from {from_q} to {to_q}.")

    @staticmethod
    def _start_date(journey: date, from_stop) -> date:
        return journey - timedelta(days=from_stop["day_offset"])

    @staticmethod
    def _runs_on(train, start: date) -> bool:
        return train["days_of_run"][start.weekday()] == "1"

    def _check_class(self, train, travel_class: str) -> str:
        cls = (travel_class or "").upper()
        if cls not in train["classes"].split(","):
            raise RailwayError(f"Class {travel_class} not available on {train['number']} (has {train['classes']}).")
        return cls

    def _inventory(self, number: str, start: date, cls: str) -> sqlite3.Row:
        key = (number, start.isoformat(), cls)
        row = self.conn.execute(
            "SELECT * FROM inventory WHERE train_number=? AND journey_date=? AND travel_class=?", key).fetchone()
        if row:
            return row
        # Deterministic initial availability so every run sees the same world.
        r = int(hashlib.md5("|".join(key).encode()).hexdigest(), 16) % 100
        cap = CLASS_INFO[cls][4] * 4
        if r < 15:
            seats, wl = 0, 5 + r * 3           # waitlisted
        elif r < 30:
            seats, wl = r - 14, 0              # 1..15 seats left
        else:
            seats, wl = 16 + (r * 7) % cap, 0
        self.conn.execute("INSERT INTO inventory VALUES (?,?,?,?,?)", (*key, seats, wl))
        return self.conn.execute(
            "SELECT * FROM inventory WHERE train_number=? AND journey_date=? AND travel_class=?", key).fetchone()

    @staticmethod
    def _status_text(inv) -> str:
        return f"AVAILABLE {inv['seats_left']}" if inv["seats_left"] > 0 else f"WL {inv['wl_count'] + 1}"

    def _fare_one(self, train, km: int, cls: str, quota: str) -> dict:
        _, rate, resv, sf, _ = CLASS_INFO[cls]
        base = max(MIN_FARE[cls], round(km * rate))
        superfast = sf if train["type"] != "Express" else 0
        tatkal = 0
        if quota == "TQ":
            tatkal = min(500, max(100, round(base * 0.3)))
        catering = 150 if train["type"] in PREMIUM_TYPES and cls != "SL" else 0
        subtotal = base + resv + superfast + tatkal + catering
        gst = round(subtotal * 0.05) if cls != "SL" else 0
        return {"base_fare": base, "reservation_charge": resv, "superfast_charge": superfast,
                "tatkal_charge": tatkal, "catering_charge": catering, "gst": gst, "total": subtotal + gst}

    @staticmethod
    def _fmt_time(start: date, hhmm: str, day_offset: int) -> str:
        d = start + timedelta(days=day_offset)
        return f"{d.isoformat()} {hhmm}"

    # ---------- tools ----------
    def search_trains(self, from_station: str, to_station: str, journey_date: str,
                      travel_class: str | None = None) -> dict:
        d = self._parse_date(journey_date)
        self._check_booking_window(d)
        from_codes, to_codes = set(self.resolve_station(from_station)), set(self.resolve_station(to_station))
        results = []
        with tx(self.conn):
            for train in self.conn.execute("SELECT * FROM trains ORDER BY number").fetchall():
                stops = self._stops(train["number"])
                seg = None
                for i, a in enumerate(stops):
                    if a["station_code"] in from_codes:
                        b = next((s for s in stops[i + 1:] if s["station_code"] in to_codes), None)
                        if b:
                            seg = (a, b)
                            break
                if not seg:
                    continue
                a, b = seg
                start = self._start_date(d, a)
                if not self._runs_on(train, start):
                    continue
                classes = train["classes"].split(",")
                if travel_class:
                    if travel_class.upper() not in classes:
                        continue
                    classes = [travel_class.upper()]
                dep = datetime.fromisoformat(self._fmt_time(start, a["dep"], a["day_offset"]))
                arr = datetime.fromisoformat(self._fmt_time(start, b["arr"], b["day_offset"]))
                mins = int((arr - dep).total_seconds() // 60)
                results.append({
                    "train_number": train["number"], "train_name": train["name"], "type": train["type"],
                    "from": a["station_code"], "from_name": self._station_name(a["station_code"]),
                    "to": b["station_code"], "to_name": self._station_name(b["station_code"]),
                    "departure": dep.strftime("%Y-%m-%d %H:%M"), "arrival": arr.strftime("%Y-%m-%d %H:%M"),
                    "duration": f"{mins // 60}h {mins % 60:02d}m", "distance_km": b["km"] - a["km"],
                    "availability": {c: self._status_text(self._inventory(train["number"], start, c))
                                     for c in classes},
                })
        results.sort(key=lambda r: r["departure"])
        return {"journey_date": d.isoformat(), "count": len(results), "trains": results}

    def check_availability(self, train_number: str, from_station: str, to_station: str,
                           journey_date: str, travel_class: str) -> dict:
        train = self._train(train_number)
        cls = self._check_class(train, travel_class)
        d = self._parse_date(journey_date)
        self._check_booking_window(d)
        a, b = self._segment(train["number"], from_station, to_station)
        start = self._start_date(d, a)
        if not self._runs_on(train, start):
            raise RailwayError(f"Train {train_number} does not run on {d} from {a['station_code']}.")
        with tx(self.conn):
            inv = self._inventory(train["number"], start, cls)
        return {"train_number": train["number"], "journey_date": d.isoformat(), "class": cls,
                "from": a["station_code"], "to": b["station_code"], "status": self._status_text(inv)}

    def get_fare(self, train_number: str, from_station: str, to_station: str,
                 travel_class: str, quota: str = "GN", passengers: int = 1) -> dict:
        train = self._train(train_number)
        cls = self._check_class(train, travel_class)
        quota = (quota or "GN").upper()
        if quota not in QUOTAS:
            raise RailwayError(f"Unknown quota {quota}. Use one of {list(QUOTAS)}.")
        a, b = self._segment(train["number"], from_station, to_station)
        one = self._fare_one(train, b["km"] - a["km"], cls, quota)
        n = max(1, int(passengers))
        return {"train_number": train["number"], "class": cls, "quota": quota, "passengers": n,
                "per_passenger": one, "total_fare": one["total"] * n, "currency": "INR",
                "note": "Simulated fare for demo purposes."}

    def book_ticket(self, train_number: str, from_station: str, to_station: str, journey_date: str,
                    travel_class: str, passengers: list[dict], quota: str = "GN") -> dict:
        train = self._train(train_number)
        cls = self._check_class(train, travel_class)
        quota = (quota or "GN").upper()
        if quota not in QUOTAS:
            raise RailwayError(f"Unknown quota {quota}.")
        d = self._parse_date(journey_date)
        self._check_booking_window(d)
        if not passengers:
            raise RailwayError("At least one passenger is required.")
        if len(passengers) > MAX_PASSENGERS[quota]:
            raise RailwayError(f"Max {MAX_PASSENGERS[quota]} passengers allowed in {QUOTAS[quota]} quota.")
        for p in passengers:
            if not str(p.get("name", "")).strip():
                raise RailwayError("Every passenger needs a name.")
            age = p.get("age")
            if not isinstance(age, int) or not 1 <= age <= 120:
                raise RailwayError(f"Invalid age for {p.get('name')}.")
            if str(p.get("gender", "")).upper() not in {"M", "F", "T"}:
                raise RailwayError(f"Gender for {p.get('name')} must be M, F or T.")
        if quota == "TQ" and (d - today()).days > 1:
            raise RailwayError("Tatkal booking opens only one day before the journey.")
        if quota == "LD" and any(str(p["gender"]).upper() != "F" for p in passengers):
            raise RailwayError("Ladies quota is only for female passengers.")
        if quota == "SS" and any(p["age"] < 60 for p in passengers):
            raise RailwayError("Senior citizen quota needs every passenger to be 60 or older.")
        a, b = self._segment(train["number"], from_station, to_station)
        start = self._start_date(d, a)
        if not self._runs_on(train, start):
            raise RailwayError(f"Train {train_number} does not run on {d} from {a['station_code']}.")
        fare = self._fare_one(train, b["km"] - a["km"], cls, quota)
        pnr = "".join(str(self.rng.randint(0, 9)) for _ in range(10))
        with tx(self.conn):
            inv = self._inventory(train["number"], start, cls)
            seats, wl = inv["seats_left"], inv["wl_count"]
            out = []
            for i, p in enumerate(passengers):
                if seats > 0:
                    coach = f"{COACH_PREFIX[cls]}{1 + (seats % 8)}"
                    status = f"CNF/{coach}/{1 + (seats * 7) % CLASS_INFO[cls][4]}"
                    seats -= 1
                else:
                    wl += 1
                    status = f"WL {wl}"
                out.append({"name": p["name"], "age": p["age"], "gender": str(p["gender"]).upper(),
                            "berth_pref": p.get("berth_pref"), "status": status})
                self.conn.execute("INSERT INTO passengers VALUES (?,?,?,?,?,?,?)",
                                  (pnr, i, p["name"], p["age"], str(p["gender"]).upper(), p.get("berth_pref"), status))
            self.conn.execute(
                "UPDATE inventory SET seats_left=?, wl_count=? WHERE train_number=? AND journey_date=? AND travel_class=?",
                (seats, wl, train["number"], start.isoformat(), cls))
            total = fare["total"] * len(passengers)
            self.conn.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (pnr, train["number"], d.isoformat(), a["station_code"], b["station_code"], cls,
                               quota, total, "BOOKED", datetime.now().isoformat(timespec="seconds")))
        return {"pnr": pnr, "train_number": train["number"], "train_name": train["name"],
                "journey_date": d.isoformat(), "from": a["station_code"], "to": b["station_code"],
                "class": cls, "quota": quota, "total_fare": total, "passengers": out}

    def pnr_status(self, pnr: str) -> dict:
        bk = self.conn.execute("SELECT * FROM bookings WHERE pnr = ?", (str(pnr).strip(),)).fetchone()
        if not bk:
            raise RailwayError(f"PNR {pnr} not found.")
        pax = self.conn.execute("SELECT * FROM passengers WHERE pnr = ? ORDER BY seq", (bk["pnr"],)).fetchall()
        train = self._train(bk["train_number"])
        return {"pnr": bk["pnr"], "booking_status": bk["status"], "train_number": bk["train_number"],
                "train_name": train["name"], "journey_date": bk["journey_date"], "from": bk["from_code"],
                "to": bk["to_code"], "class": bk["travel_class"], "quota": bk["quota"],
                "total_fare": bk["total_fare"],
                "passengers": [{"name": p["name"], "age": p["age"], "status": p["status"]} for p in pax]}

    def cancel_ticket(self, pnr: str) -> dict:
        bk = self.conn.execute("SELECT * FROM bookings WHERE pnr = ?", (str(pnr).strip(),)).fetchone()
        if not bk:
            raise RailwayError(f"PNR {pnr} not found.")
        if bk["status"] == "CANCELLED":
            raise RailwayError(f"PNR {pnr} is already cancelled.")
        pax = self.conn.execute("SELECT * FROM passengers WHERE pnr = ?", (bk["pnr"],)).fetchall()
        per = bk["total_fare"] / len(pax)
        refund, freed = 0.0, 0
        for p in pax:
            if p["status"].startswith("CNF"):
                freed += 1
                refund += 0 if bk["quota"] == "TQ" else max(0, per - CANCEL_CHARGE[bk["travel_class"]])
            else:
                refund += max(0, per - 60)
        a, _ = self._segment(bk["train_number"], bk["from_code"], bk["to_code"])
        start = self._start_date(date.fromisoformat(bk["journey_date"]), a)
        with tx(self.conn):
            self.conn.execute("UPDATE bookings SET status='CANCELLED' WHERE pnr=?", (bk["pnr"],))
            self.conn.execute("UPDATE passengers SET status='CANCELLED' WHERE pnr=?", (bk["pnr"],))
            self.conn.execute(
                "UPDATE inventory SET seats_left = seats_left + ? WHERE train_number=? AND journey_date=? AND travel_class=?",
                (freed, bk["train_number"], start.isoformat(), bk["travel_class"]))
        return {"pnr": bk["pnr"], "status": "CANCELLED", "refund_amount": round(refund, 2), "currency": "INR",
                "note": "Tatkal confirmed tickets get no refund." if bk["quota"] == "TQ" else None}
