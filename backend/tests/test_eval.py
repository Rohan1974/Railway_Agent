import json
import random
from types import SimpleNamespace as NS

import pytest

from app.agents.claude_agent import ClaudeAgent
from app.config import Settings, settings
from app.decisions.claude_decider import build_prompt, parse_label
from app.decisions.tasks import TASKS
from app.railway.service import RailwayError, RailwayService
from eval import bench_scenarios, run as run_cli
from eval.common import DATASETS, load_jsonl

DECISIONS = load_jsonl(DATASETS / "decisions.jsonl")
SCEN = json.loads((DATASETS / "scenarios.json").read_text(encoding="utf-8"))
EXPECT_KEYS = {"booking", "no_new_booking", "tools_called", "tools_called_any", "tools_not_called", "no_tools",
               "tool_args", "cancelled", "not_cancelled", "reply_contains_any"}


# ---------- dataset sanity ----------
def test_decision_rows_are_valid():
    ids = [r["id"] for r in DECISIONS]
    assert len(ids) == len(set(ids))
    assert len(DECISIONS) >= 200
    for r in DECISIONS:
        assert r["task"] in TASKS, r
        assert r["label"] in TASKS[r["task"]].options, r
        assert r["text"].strip()
        assert ("context" in r) == TASKS[r["task"]].uses_context, r


def test_every_label_has_examples():
    for name, task in TASKS.items():
        seen = {r["label"] for r in DECISIONS if r["task"] == name}
        missing = set(task.options) - seen
        assert not missing or name == "travel_class" and missing <= {"none"}, (name, missing)


def test_scenarios_are_valid_and_feasible(svc, conn):
    ids = [s["id"] for s in SCEN["scenarios"]]
    assert len(ids) == len(set(ids))
    trains = {r["number"] for r in conn.execute("SELECT number FROM trains")}
    for s in SCEN["scenarios"]:
        assert set(s["expect"]) <= EXPECT_KEYS, s["id"]
        b = s["expect"].get("booking")
        if b:
            # the expected booking must actually be bookable in the mock world on the pinned date
            assert b["train_number"] in trains, s["id"]
            row = conn.execute("SELECT station_code FROM train_stops WHERE train_number=? ORDER BY seq",
                               (b["train_number"],)).fetchall()
            frm = b.get("from_code", row[0]["station_code"])
            to = b.get("to_code", row[-1]["station_code"])
            pax = [{"name": f"P{i}", "age": 70, "gender": "F"} for i in range(b["passengers"])]
            svc.book_ticket(b["train_number"], frm, to, b["journey_date"], b["travel_class"], pax, b.get("quota", "GN"))


@pytest.mark.parametrize("sid", ["S17-past-date", "S24-tatkal-too-early"])
def test_edge_scenarios_are_really_rejected(svc, sid):
    pax = [{"name": "Rohan Patole", "age": 28, "gender": "M"}]
    args = {"S17-past-date": ("12123", "CSMT", "PUNE", "2026-10-01", "CC", pax, "GN"),
            "S24-tatkal-too-early": ("12123", "CSMT", "PUNE", "2026-10-28", "CC", pax, "TQ")}[sid]
    with pytest.raises(RailwayError):
        svc.book_ticket(*args)


# ---------- classifier ----------
def test_prompt_lists_all_options():
    for name, t in TASKS.items():
        p = build_prompt(name)
        assert all(f"- {k}:" in p for k in t.options)


def test_parse_label():
    assert parse_label('{"label": "pnr_status"}', "intent") == "pnr_status"
    assert parse_label('Sure!\n```json\n{"label": "3A"}\n```', "travel_class") == "3A"
    assert parse_label('{"label": "flight"}', "intent") is None
    assert parse_label("no json here", "quota") is None


# ---------- CLI end to end (fake model, temp DB) ----------
@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    old = settings.db_path
    object.__setattr__(settings, "db_path", tmp_path / "bench.db")
    monkeypatch.setattr(run_cli, "RESULTS", tmp_path / "results")
    yield tmp_path
    object.__setattr__(settings, "db_path", old)


def test_decisions_cli_fake(tmp_db, capsys):
    run_cli.main(["decisions", "--fake", "--limit", "12", "--repeats", "2"])
    out_dirs = list((tmp_db / "results").iterdir())
    assert len(out_dirs) == 1 and out_dirs[0].name.startswith("fake-decisions-")
    rows = load_jsonl(out_dirs[0] / "rows.jsonl")
    assert len(rows) == 24 and all(r["error"] is None for r in rows)
    summary = json.loads((out_dirs[0] / "summary.json").read_text())
    assert summary["meta"]["fake"] is True and summary["summary"]["A"]["decisions"] == 24
    from app.db import connect
    c = connect(tmp_db / "bench.db")
    assert c.execute("SELECT status, fake FROM runs").fetchone()[:] == ("done", 1)
    assert c.execute("SELECT COUNT(*) FROM model_calls WHERE step LIKE 'decision:%'").fetchone()[0] == 24


def test_mode_b_refused_without_jev_key(tmp_db):
    with pytest.raises(SystemExit, match="JEV_API_KEY"):
        run_cli.main(["decisions", "--fake", "--modes", "A,B"])


# ---------- scenario runner with a scripted Claude ----------
class ScriptedBooker:
    """Books on any user message containing 'yes', otherwise just replies."""
    def __init__(self, book_args):
        self.book_args = book_args

    def create(self, messages, **kw):
        u = NS(input_tokens=1000, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0,
               output_tokens_details=None)
        last = messages[-1]["content"]
        if isinstance(last, str) and "yes" in last.lower():
            return NS(stop_reason="tool_use", usage=u,
                      content=[NS(type="tool_use", id="t1", name="book_ticket", input=self.book_args)])
        return NS(stop_reason="end_turn", usage=u, content=[NS(type="text", text="Done.")])


def test_scenario_runner_judges_end_state(conn, telemetry):
    sc = next(s for s in SCEN["scenarios"] if s["id"] == "S06-book-en-full-details")
    good = {"train_number": "11007", "from_station": "CSMT", "to_station": "PUNE", "journey_date": "2026-10-25",
            "travel_class": "3A", "quota": "GN", "passengers": [{"name": "Rohan Patole", "age": 28, "gender": "M"},
                                                              {"name": "Priya Patole", "age": 26, "gender": "F"}]}
    wrong = {**good, "travel_class": "SL"}  # 11007 has SL too, so this books, but the wrong class

    def runner(args):
        client = NS(messages=ScriptedBooker(args))
        make = lambda mode, service: ClaudeAgent(client, service, telemetry, Settings(anthropic_api_key="x"))
        return bench_scenarios.run([sc], ["A"], make_agent=make, telemetry_conn=conn, run_id="t",
                                   repeats=1, today=SCEN["today"])[0]

    ok = runner(good)
    assert ok["success"], ok["checks"]
    assert ok["llm_calls"] == 3 and ok["tool_calls"] == 1 and ok["cost_usd"] > 0
    bad = runner(wrong)
    assert not bad["success"]
    assert "travel_class" in bad["checks"][0]["detail"]
    s = bench_scenarios.summarize([ok, bad])["A"]
    assert s["success_rate"] == 0.5 and len(s["failures"]) == 1
