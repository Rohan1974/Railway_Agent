"""Scenario benchmark: scripted multi-turn conversations, judged on the final state of the mock railway DB."""
from __future__ import annotations

import os
import random
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Callable

from app.db import connect
from app.railway.seed import seed
from app.railway.service import RailwayService

from .checks import run_checks
from .common import latency_stats, mode_order

SEED = 7


def _fill(obj, pnrs: list[str]):
    """Replace {pnr0}, {pnr1}... placeholders anywhere in the scenario."""
    if isinstance(obj, str):
        for i, p in enumerate(pnrs):
            obj = obj.replace(f"{{pnr{i}}}", p)
        return obj
    if isinstance(obj, list):
        return [_fill(x, pnrs) for x in obj]
    if isinstance(obj, dict):
        return {k: _fill(v, pnrs) for k, v in obj.items()}
    return obj


def run_one(scenario: dict, mode: str, rep: int, *, make_agent: Callable, telemetry_conn: sqlite3.Connection,
            run_id: str, tmpdir: Path) -> dict:
    rconn = connect(tmpdir / f"{scenario['id']}-{mode}-{rep}.db")   # fresh railway world per run
    seed(rconn)
    service = RailwayService(rconn, rng=random.Random(SEED))
    pnrs = [service.book_ticket(**b)["pnr"] for b in scenario.get("setup", {}).get("bookings", [])]
    sc = _fill(scenario, pnrs)
    agent = make_agent(mode, service)
    conv = f"{run_id}:{sc['id']}:{mode}:{rep}"
    turns, error = [], None
    for text in sc["turns"]:
        try:
            out = agent.chat(text, conversation_id=conv, run_id=run_id)
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {e}"
            break
        turns.append({"user": text, "reply": out["reply"], **out["metrics"]})
    last = turns[-1]["reply"] if turns else ""
    checks = run_checks(sc["expect"], rconn=rconn, tconn=telemetry_conn, conversation_id=conv,
                        setup_pnrs=pnrs, last_reply=last) if error is None else []
    rconn.close()
    return {
        "id": sc["id"], "category": sc["category"], "lang": sc["lang"], "mode": mode, "repeat": rep,
        "success": error is None and all(c[1] for c in checks),
        "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in checks],
        "error": error, "turns": turns,
        "latency_ms": sum(t["latency_ms"] for t in turns), "cost_usd": sum(t["cost_usd"] for t in turns),
        "llm_calls": sum(t["llm_calls"] for t in turns), "decision_calls": sum(t["decision_calls"] for t in turns),
        "tool_calls": sum(t["tool_calls"] for t in turns),
    }


def run(scenarios: list[dict], modes: list[str], *, make_agent: Callable, telemetry_conn: sqlite3.Connection,
        run_id: str, repeats: int, today: str, on_row: Callable[[dict], None] | None = None) -> list[dict]:
    prev = os.environ.get("TODAY")
    os.environ["TODAY"] = today
    try:
        out = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, sc in enumerate(scenarios):
                for rep in range(repeats):
                    for mode in mode_order(modes, i + rep):
                        rec = run_one(sc, mode, rep, make_agent=make_agent, telemetry_conn=telemetry_conn,
                                      run_id=run_id, tmpdir=Path(tmp))
                        out.append(rec)
                        if on_row:
                            on_row(rec)
        return out
    finally:
        if prev is None:
            os.environ.pop("TODAY", None)
        else:
            os.environ["TODAY"] = prev


def summarize(results: list[dict]) -> dict:
    by_mode: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_mode[r["mode"]].append(r)
    summary = {}
    for mode, rs in by_mode.items():
        cats = defaultdict(list)
        for r in rs:
            cats[r["category"]].append(r)
        rate = lambda xs: sum(x["success"] for x in xs) / len(xs) if xs else None
        turn_lat = [t["latency_ms"] for r in rs for t in r["turns"]]
        n = len(rs)
        summary[mode] = {
            "runs": n, "errors": sum(1 for r in rs if r["error"]),
            "success_rate": rate(rs),
            "by_category": {c: {"n": len(v), "success_rate": rate(v)} for c, v in sorted(cats.items())},
            "turn_latency_ms": latency_stats(turn_lat),
            "scenario_latency_ms": latency_stats([r["latency_ms"] for r in rs]),
            "cost_usd": {"total": sum(r["cost_usd"] for r in rs), "per_scenario": sum(r["cost_usd"] for r in rs) / n},
            "llm_calls_per_scenario": sum(r["llm_calls"] for r in rs) / n,
            "decision_calls_per_scenario": sum(r["decision_calls"] for r in rs) / n,
            "failures": [{"id": r["id"], "repeat": r["repeat"], "error": r["error"],
                          "failed_checks": [c for c in r["checks"] if not c["passed"]]}
                         for r in rs if not r["success"]],
        }
    return summary
