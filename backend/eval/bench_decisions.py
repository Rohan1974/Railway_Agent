"""Decision benchmark: the same labelled classification rows answered by Mode A (Claude) and Mode B (Jev)."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from app.telemetry import TurnContext

from .common import latency_stats, mode_order

MODE_NAMES = {"A": "A_llm_only", "B": "B_jev_llm"}


def run(rows: list[dict], deciders: dict, *, run_id: str, repeats: int,
        on_row: Callable[[dict], None] | None = None, max_consecutive_errors: int = 5) -> list[dict]:
    out, errors_in_a_row = [], 0
    modes = list(deciders)
    for i, row in enumerate(rows):
        for rep in range(repeats):
            for mode in mode_order(modes, i + rep):
                ctx = TurnContext(mode=MODE_NAMES[mode], conversation_id=f"{run_id}:{row['id']}:{rep}", run_id=run_id)
                rec = {"id": row["id"], "task": row["task"], "lang": row["lang"], "mode": mode, "repeat": rep,
                       "gold": row["label"]}
                try:
                    d = deciders[mode].decide(ctx, row["task"], row["text"], row.get("context"))
                    rec.update(pred=d.label, correct=d.label == row["label"], invalid=d.label is None,
                               confidence=d.confidence, latency_ms=d.latency_ms, cost_usd=d.cost_usd,
                               raw=d.raw[:300], error=None)
                    errors_in_a_row = 0
                except Exception as e:  # noqa: BLE001 - keep going, record the failure
                    rec.update(pred=None, correct=False, invalid=True, confidence=None, latency_ms=None,
                               cost_usd=0.0, raw="", error=f"{type(e).__name__}: {e}")
                    errors_in_a_row += 1
                out.append(rec)
                if on_row:
                    on_row(rec)
                if errors_in_a_row >= max_consecutive_errors:
                    raise RuntimeError(f"Stopping: {errors_in_a_row} errors in a row. Last: {rec['error']}")
    return out


def summarize(results: list[dict]) -> dict:
    by_mode: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_mode[r["mode"]].append(r)
    summary = {}
    for mode, rs in by_mode.items():
        ok = [r for r in rs if r["error"] is None]
        tasks = defaultdict(list)
        langs = defaultdict(list)
        for r in rs:
            tasks[r["task"]].append(r)
            langs[r["lang"]].append(r)
        acc = lambda xs: sum(x["correct"] for x in xs) / len(xs) if xs else None
        summary[mode] = {
            "decisions": len(rs), "errors": len(rs) - len(ok),
            "accuracy": acc(rs),
            "macro_accuracy_by_task": sum(acc(v) for v in tasks.values()) / len(tasks),
            "by_task": {t: {"n": len(v), "accuracy": acc(v), "invalid": sum(x["invalid"] for x in v)}
                        for t, v in sorted(tasks.items())},
            "by_lang": {l: {"n": len(v), "accuracy": acc(v)} for l, v in sorted(langs.items())},
            "latency_ms": latency_stats([r["latency_ms"] for r in ok]),
            "cost_usd": {"total": sum(r["cost_usd"] for r in rs),
                         "per_decision": sum(r["cost_usd"] for r in ok) / len(ok) if ok else None},
        }
    return summary
