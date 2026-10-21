# RailSaathi: LLM-only vs Jev + LLM

A railway ticket booking agent built twice, to measure what a System 1 decision model (Jev) saves
when it takes over the classification steps from an LLM.

- **Mode A**: Claude Sonnet 5.5 does everything.
- **Mode B**: Jev does the classification steps (intent, class, quota, confirmations, routing); Claude does the rest.

Both modes use the same tools, prompts, model and settings. Every model call is logged with tokens,
latency and cost, so every number on the dashboard can be traced to raw rows.

> Railway data is mock data. Station codes and train numbers are real, but timings, seats and fares are simulated.

## Setup (Windows, uses uv)

Install uv once (if you don't have it):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then:

```powershell
cd D:\JEV\Railway_Agent
copy .env.example .env             # then put your ANTHROPIC_API_KEY in .env
cd backend
uv sync                            # creates .venv and installs exact versions from uv.lock
uv run python -m app.railway.seed  # creates data\railway.db
uv run pytest                      # 26 tests
uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

Add a package: `uv add <name>` (dev-only: `uv add --dev <name>`). Don't use pip.

## Benchmarks

Two benchmarks, both run from `backend/`:

| Bench | What it measures | Data |
|---|---|---|
| `decisions` | The classification steps alone: accuracy, latency and cost per decision, Claude vs Jev on identical questions | `eval/datasets/decisions.jsonl`: 215 labelled rows (intent, class, quota, confirmation, frustration) in English, Hindi and Marathi |
| `scenarios` | The whole agent: task success, latency per turn, cost per conversation | `eval/datasets/scenarios.json`: 24 scripted conversations judged on the final DB state |

```powershell
uv run python -m eval.run decisions --fake --yes          # offline pipeline check (no API cost)
uv run python -m eval.run decisions --limit 20            # small real run first
uv run python -m eval.run decisions --repeats 3           # full run
uv run python -m eval.run scenarios --ids S01-search-en,S06-book-en-full-details
uv run python -m eval.run scenarios --repeats 3
```

Each run gets a `run_id` and is recorded in the `runs` table with the model, effort, dataset hash and git
commit. Raw rows go to `eval/results/<run_id>/rows.jsonl` and the summary to `summary.json`. Fake runs are
marked `fake-…` and are not committed. `--modes A,B` needs Jev API access.

## API

| Endpoint | What it does |
|---|---|
| `GET /health` | Model, effort, whether Jev key is set |
| `GET /api/stations` | All stations |
| `POST /api/tools/{name}` | Call a railway tool directly, no model (`{"args": {...}}`) |
| `POST /api/chat` | `{"message": "...", "mode": "A", "conversation_id": null}` |
| `GET /api/metrics/summary` | p50/p95 latency, cost per turn, calls per turn, by mode |
| `GET /api/metrics/calls` | Raw model call log |

## Project layout

```
backend/app/
  config.py            settings + price table (with source and date)
  db.py                SQLite schema (railway data + telemetry)
  telemetry.py         per-call logging and cost calculation
  railway/             mock data, service, tool schemas
  agents/              Mode A agent (Mode B coming)
  decisions/           classification tasks, Claude classifier, Jev adapter (pending access)
backend/eval/          benchmark datasets, runner, checks, results
backend/tests/         pytest suite
frontend/              React chat UI + dashboard (coming)
```

See `railway-agent-plan.md` for the full plan.
