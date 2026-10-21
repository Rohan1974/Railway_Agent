"""Telemetry: every model call, tool call and user turn is logged with tokens, latency and cost.

Cost is always computed from the token counts the provider returns x the PRICES table in config.py,
so the dashboard numbers can be traced back to raw rows.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import PRICES
from .db import tx


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class Usage:
    input_tokens: int = 0          # uncached input
    output_tokens: int = 0         # includes thinking tokens (billing total)
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0    # 5-minute cache writes
    thinking_tokens: int = 0       # informational, already inside output_tokens

    @classmethod
    def from_anthropic(cls, usage: Any) -> "Usage":
        g = lambda obj, k: (getattr(obj, k, None) if not isinstance(obj, dict) else obj.get(k)) or 0
        details = getattr(usage, "output_tokens_details", None) if not isinstance(usage, dict) \
            else usage.get("output_tokens_details")
        return cls(input_tokens=g(usage, "input_tokens"), output_tokens=g(usage, "output_tokens"),
                   cache_read_tokens=g(usage, "cache_read_input_tokens"),
                   cache_write_tokens=g(usage, "cache_creation_input_tokens"),
                   thinking_tokens=g(details, "thinking_tokens") if details else 0)


def cost_usd(model: str, u: Usage) -> float:
    p = PRICES.get(model)
    if p is None:
        raise KeyError(f"No price for model '{model}'. Add it to PRICES in config.py.")
    return (u.input_tokens * p.input + u.output_tokens * p.output + u.cache_read_tokens * p.cache_read
            + u.cache_write_tokens * p.cache_write_5m) / 1_000_000


@dataclass
class TurnContext:
    mode: str
    conversation_id: str
    run_id: str | None = None
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.perf_counter)
    cost: float = 0.0
    llm_calls: int = 0
    decision_calls: int = 0
    tool_calls: int = 0


class Telemetry:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def model_call(self, ctx: TurnContext, *, step: str, provider: str, model: str, usage: Usage,
                   latency_ms: float, ok: bool = True, error: str | None = None, kind: str = "llm") -> float:
        c = cost_usd(model, usage)
        ctx.cost += c
        if kind == "llm":
            ctx.llm_calls += 1
        else:
            ctx.decision_calls += 1
        with tx(self.conn):
            self.conn.execute(
                "INSERT INTO model_calls (ts, run_id, conversation_id, turn_id, mode, step, provider, model,"
                " input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, thinking_tokens,"
                " latency_ms, cost_usd, ok, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (_now(), ctx.run_id, ctx.conversation_id, ctx.turn_id, ctx.mode, step, provider, model,
                 usage.input_tokens, usage.output_tokens, usage.cache_read_tokens, usage.cache_write_tokens,
                 usage.thinking_tokens, latency_ms, c, int(ok), error))
        return c

    def tool_call(self, ctx: TurnContext, tool: str, latency_ms: float, ok: bool,
                  args: dict | None = None) -> None:
        ctx.tool_calls += 1
        with tx(self.conn):
            self.conn.execute(
                "INSERT INTO tool_calls (ts, run_id, conversation_id, turn_id, mode, tool, latency_ms, ok, args)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (_now(), ctx.run_id, ctx.conversation_id, ctx.turn_id, ctx.mode, tool, latency_ms, int(ok),
                 json.dumps(args, ensure_ascii=False) if args is not None else None))

    def finish_turn(self, ctx: TurnContext, user_text: str, reply_text: str) -> dict:
        latency = (time.perf_counter() - ctx.started) * 1000
        with tx(self.conn):
            self.conn.execute(
                "INSERT INTO turns VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ctx.turn_id, _now(), ctx.run_id, ctx.conversation_id, ctx.mode, user_text, reply_text,
                 latency, ctx.cost, ctx.llm_calls, ctx.decision_calls, ctx.tool_calls))
        return {"turn_id": ctx.turn_id, "latency_ms": round(latency, 1), "cost_usd": round(ctx.cost, 6),
                "llm_calls": ctx.llm_calls, "decision_calls": ctx.decision_calls, "tool_calls": ctx.tool_calls}

    # ---------- reporting ----------
    @staticmethod
    def _pct(values: list[float], p: float) -> float | None:
        if not values:
            return None
        s = sorted(values)
        k = (len(s) - 1) * p
        lo, hi = int(k), min(int(k) + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (k - lo)

    def summary(self, run_id: str | None = None) -> dict:
        where, params = ("WHERE run_id = ?", (run_id,)) if run_id else ("", ())
        out = {}
        for mode in [r["mode"] for r in self.conn.execute(f"SELECT DISTINCT mode FROM turns {where}", params)]:
            q = f"SELECT * FROM turns {'WHERE' if not where else where + ' AND'} mode = ?"
            rows = self.conn.execute(q, (*params, mode)).fetchall()
            lat = [r["latency_ms"] for r in rows]
            cost = [r["cost_usd"] for r in rows]
            out[mode] = {
                "turns": len(rows),
                "latency_ms": {"p50": self._pct(lat, .5), "p95": self._pct(lat, .95), "mean": sum(lat) / len(lat)},
                "cost_usd": {"total": sum(cost), "mean_per_turn": sum(cost) / len(cost)},
                "llm_calls_per_turn": sum(r["llm_calls"] for r in rows) / len(rows),
                "decision_calls_per_turn": sum(r["decision_calls"] for r in rows) / len(rows),
            }
        return out
