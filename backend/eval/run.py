"""Benchmark CLI. Run from backend/:

  uv run python -m eval.run decisions --limit 20            # quick real run, Mode A
  uv run python -m eval.run decisions --repeats 3           # full decision benchmark
  uv run python -m eval.run scenarios --ids S01-search-en,S06-book-en-full-details
  uv run python -m eval.run scenarios --repeats 3
  uv run python -m eval.run decisions --fake --yes          # offline pipeline check, no API cost

Mode B (--modes A,B) needs JEV_API_KEY and the Jev adapter; until then only A runs.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from app.config import settings
from app.db import connect, init_schema, tx
from app.telemetry import Telemetry

from . import bench_decisions, bench_scenarios
from .common import DATASETS, RESULTS, file_sha, git_commit, load_jsonl, new_run_id

DECISIONS_FILE = DATASETS / "decisions.jsonl"
SCENARIOS_FILE = DATASETS / "scenarios.json"


def _client(fake: bool, kind: str):
    if fake:
        from .fakes import fake_client
        return fake_client(kind)
    if not settings.anthropic_api_key:
        sys.exit("ANTHROPIC_API_KEY is not set in .env")
    import anthropic
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=3)


def _check_modes(modes: list[str]) -> None:
    for m in modes:
        if m not in ("A", "B"):
            sys.exit(f"Unknown mode {m}. Use A and/or B.")
    if "B" in modes and not settings.jev_api_key:
        sys.exit("Mode B needs JEV_API_KEY (Jev API access). Run with --modes A for now.")


def _confirm(msg: str, yes: bool) -> None:
    print(msg)
    if not yes and input("Continue? [y/N] ").strip().lower() != "y":
        sys.exit("Cancelled.")


def _pct(x):
    return "-" if x is None else f"{x * 100:.1f}%"


def _ms(x):
    return "-" if x is None else f"{x:,.0f} ms"


def _usd(x):
    return "-" if x is None else f"${x:.5f}"


def print_decisions(summary: dict) -> None:
    for mode, s in summary.items():
        print(f"\n=== Mode {mode}: {s['decisions']} decisions, {s['errors']} errors ===")
        print(f"accuracy {_pct(s['accuracy'])} | macro by task {_pct(s['macro_accuracy_by_task'])}")
        print(f"latency p50 {_ms(s['latency_ms']['p50'])} | p95 {_ms(s['latency_ms']['p95'])}")
        print(f"cost per decision {_usd(s['cost_usd']['per_decision'])} | total {_usd(s['cost_usd']['total'])}")
        for t, v in s["by_task"].items():
            print(f"  {t:<14} n={v['n']:<4} acc={_pct(v['accuracy']):>7}  invalid={v['invalid']}")


def print_scenarios(summary: dict) -> None:
    for mode, s in summary.items():
        print(f"\n=== Mode {mode}: {s['runs']} scenario runs, {s['errors']} errors ===")
        print(f"task success {_pct(s['success_rate'])}")
        print(f"turn latency p50 {_ms(s['turn_latency_ms']['p50'])} | p95 {_ms(s['turn_latency_ms']['p95'])}")
        print(f"cost per scenario {_usd(s['cost_usd']['per_scenario'])} | total {_usd(s['cost_usd']['total'])}"
              f" | LLM calls per scenario {s['llm_calls_per_scenario']:.1f}")
        for c, v in s["by_category"].items():
            print(f"  {c:<13} n={v['n']:<3} success={_pct(v['success_rate'])}")
        for f in s["failures"]:
            why = f["error"] or "; ".join(f"{c['name']}: {c['detail']}" for c in f["failed_checks"])
            print(f"  FAIL {f['id']} (rep {f['repeat']}): {why[:200]}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="LLM-only vs Jev+LLM benchmarks")
    ap.add_argument("bench", choices=["decisions", "scenarios"])
    ap.add_argument("--modes", default="A", help="A, B or A,B (default A)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--limit", type=int, help="only the first N rows/scenarios")
    ap.add_argument("--tasks", help="decisions: comma-separated task names")
    ap.add_argument("--ids", help="scenarios: comma-separated scenario ids")
    ap.add_argument("--fake", action="store_true", help="offline fake model (no API calls, results marked fake)")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args(argv)

    modes = [m.strip().upper() for m in args.modes.split(",") if m.strip()]
    _check_modes(modes)
    tconn = connect()
    init_schema(tconn)
    telemetry = Telemetry(tconn)
    run_id = new_run_id(args.bench, args.fake)

    if args.bench == "decisions":
        rows = load_jsonl(DECISIONS_FILE)
        if args.tasks:
            keep = set(args.tasks.split(","))
            rows = [r for r in rows if r["task"] in keep]
        rows = rows[: args.limit] if args.limit else rows
        n_calls = len(rows) * args.repeats * len(modes)
        sha = file_sha(DECISIONS_FILE)
        items = len(rows)
    else:
        data = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))
        scenarios = data["scenarios"]
        if args.ids:
            keep = set(args.ids.split(","))
            scenarios = [s for s in scenarios if s["id"] in keep]
        scenarios = scenarios[: args.limit] if args.limit else scenarios
        n_turns = sum(len(s["turns"]) for s in scenarios) * args.repeats * len(modes)
        sha = file_sha(SCENARIOS_FILE)
        items = len(scenarios)

    if items == 0:
        sys.exit("Nothing to run (check --tasks / --ids / --limit).")
    what = (f"{n_calls} classification calls" if args.bench == "decisions"
            else f"{items} scenarios, {n_turns} user turns (each turn = 1+ Claude calls)")
    _confirm(f"Run {run_id}: {what}; modes {modes}, model {settings.claude_model}, effort {settings.claude_effort}"
             f"{' [FAKE]' if args.fake else ''}", args.yes or args.fake)

    with tx(tconn):
        tconn.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (run_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), args.bench, ",".join(modes),
                       settings.claude_model, settings.claude_effort, args.repeats, items, sha, git_commit(),
                       int(args.fake), "running", None))

    out_dir = RESULTS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_file = (out_dir / "rows.jsonl").open("w", encoding="utf-8")
    done = {"n": 0}

    def on_row(rec):
        rows_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
        rows_file.flush()
        done["n"] += 1
        mark = "ok " if rec.get("correct", rec.get("success")) else "XX "
        print(f"\r{done['n']} done | last: {mark}{rec['id']} [{rec['mode']}]", end="", flush=True)

    status = "done"
    try:
        if args.bench == "decisions":
            from app.decisions.claude_decider import ClaudeDecider
            deciders = {}
            for m in modes:
                if m == "A":
                    deciders[m] = ClaudeDecider(_client(args.fake, "decisions"), telemetry, settings)
                else:
                    from app.decisions.jev_decider import JevDecider
                    deciders[m] = JevDecider(telemetry, settings)
            results = bench_decisions.run(rows, deciders, run_id=run_id, repeats=args.repeats, on_row=on_row)
            summary = bench_decisions.summarize(results)
        else:
            from app.agents.claude_agent import ClaudeAgent
            client = _client(args.fake, "scenarios")

            def make_agent(mode, service):
                if mode == "A":
                    return ClaudeAgent(client, service, telemetry, settings)
                raise NotImplementedError("Mode B agent is not built yet.")

            results = bench_scenarios.run(scenarios, modes, make_agent=make_agent, telemetry_conn=tconn,
                                          run_id=run_id, repeats=args.repeats, today=data["today"], on_row=on_row)
            summary = bench_scenarios.summarize(results)
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except Exception:
        status = "failed"
        raise
    finally:
        rows_file.close()
        print()
        with tx(tconn):
            tconn.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))

    meta = {"run_id": run_id, "bench": args.bench, "modes": modes, "model": settings.claude_model,
            "effort": settings.claude_effort, "repeats": args.repeats, "items": items, "dataset_sha": sha,
            "git_commit": git_commit(), "fake": args.fake}
    (out_dir / "summary.json").write_text(json.dumps({"meta": meta, "summary": summary}, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    with tx(tconn):
        tconn.execute("UPDATE runs SET summary_json = ? WHERE run_id = ?", (json.dumps(summary), run_id))
    (print_decisions if args.bench == "decisions" else print_scenarios)(summary)
    print(f"\nSaved: {out_dir}")


if __name__ == "__main__":
    main()
