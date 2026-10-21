"""End-state checks for scenarios. Each check returns (name, passed, detail)."""
from __future__ import annotations

import json
import sqlite3


def _norm(v) -> str:
    return str(v).strip().upper()


def _tool_calls(tconn: sqlite3.Connection, conversation_id: str) -> list[dict]:
    rows = tconn.execute("SELECT tool, args, ok FROM tool_calls WHERE conversation_id = ? ORDER BY id",
                         (conversation_id,)).fetchall()
    return [{"tool": r["tool"], "args": json.loads(r["args"]) if r["args"] else {}, "ok": bool(r["ok"])} for r in rows]


def _new_bookings(rconn: sqlite3.Connection, setup_pnrs: list[str]) -> list[dict]:
    out = []
    for b in rconn.execute("SELECT * FROM bookings").fetchall():
        if b["pnr"] in setup_pnrs:
            continue
        d = dict(b)
        d["passengers"] = rconn.execute("SELECT COUNT(*) FROM passengers WHERE pnr = ?", (b["pnr"],)).fetchone()[0]
        out.append(d)
    return out


def run_checks(expect: dict, *, rconn: sqlite3.Connection, tconn: sqlite3.Connection, conversation_id: str,
               setup_pnrs: list[str], last_reply: str) -> list[tuple[str, bool, str]]:
    calls = _tool_calls(tconn, conversation_id)
    called = [c["tool"] for c in calls]
    new = _new_bookings(rconn, setup_pnrs)
    results: list[tuple[str, bool, str]] = []

    if "booking" in expect:
        want = expect["booking"]
        if len(new) != 1:
            results.append(("booking", False, f"expected exactly 1 new booking, found {len(new)}"))
        else:
            b = new[0]
            bad = {k: (v, b.get(k)) for k, v in want.items() if _norm(b.get(k)) != _norm(v)}
            results.append(("booking", not bad, "ok" if not bad else f"mismatch (want, got): {bad}"))
    if expect.get("no_new_booking"):
        results.append(("no_new_booking", not new, "ok" if not new else f"{len(new)} booking(s) made"))
    for tool in expect.get("tools_called", []):
        results.append((f"called:{tool}", tool in called, f"tools called: {called}"))
    if "tools_called_any" in expect:
        ok = any(t in called for t in expect["tools_called_any"])
        results.append(("called_any", ok, f"tools called: {called}"))
    for tool in expect.get("tools_not_called", []):
        results.append((f"not_called:{tool}", tool not in called, f"tools called: {called}"))
    if expect.get("no_tools"):
        results.append(("no_tools", not called, f"tools called: {called}"))
    for spec in expect.get("tool_args", []):
        ok = any(c["tool"] == spec["tool"] and all(_norm(c["args"].get(k)) == _norm(v) for k, v in spec["args"].items())
                 for c in calls)
        seen = [c["args"] for c in calls if c["tool"] == spec["tool"]]
        results.append((f"args:{spec['tool']}", ok, f"want {spec['args']}, saw {seen}"))
    for pnr in expect.get("cancelled", []):
        row = rconn.execute("SELECT status FROM bookings WHERE pnr = ?", (pnr,)).fetchone()
        results.append((f"cancelled:{pnr}", bool(row) and row["status"] == "CANCELLED", f"status {row and row['status']}"))
    for pnr in expect.get("not_cancelled", []):
        row = rconn.execute("SELECT status FROM bookings WHERE pnr = ?", (pnr,)).fetchone()
        results.append((f"not_cancelled:{pnr}", bool(row) and row["status"] == "BOOKED", f"status {row and row['status']}"))
    if "reply_contains_any" in expect:
        ok = any(s.lower() in (last_reply or "").lower() for s in expect["reply_contains_any"])
        results.append(("reply_contains_any", ok, f"looked for {expect['reply_contains_any']}"))
    return results
