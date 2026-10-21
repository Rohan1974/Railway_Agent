# Railway Ticket Booking Agent — LLM vs Jev+LLM Benchmark (Plan)

## Decisions
- LLM: Claude Sonnet 5.5 (`claude-sonnet-5-5`, set in .env), same model and same `effort` setting for both modes.
  Sonnet 5.5 rejects `temperature`/`top_p`/`top_k` (400 error), so we hold `effort` constant instead (set via CLAUDE_EFFORT in .env).
  Adaptive thinking is on by default; thinking tokens are billed as output and are logged separately.
- Stack: Python FastAPI backend (managed with uv, no pip) + React (Recharts) frontend
- Data: realistic mock railway data (real station codes/trains, simulated seats/PNR) in SQLite, fixed seed
- Jev: no API access yet → build a pluggable `DecisionModel` interface; plug Jev in when access arrives. Never publish estimated Jev numbers as measured.

## Two modes
- Mode A (LLM-only): Claude does intent classification, extraction, reasoning, tool calls, reply.
- Mode B (Jev + LLM): Jev does the classification tasks; Claude does extraction, multi-step reasoning, tool calls, and replies.

## Task split in Mode B

Rule of thumb: if the question is "yes/no, which option, or how much (score)" → Jev. If something must be written, extracted, or reasoned about → LLM.

### Jev tasks (fast, cheap, typed output)

| Task | Jev question type | Example input → output |
|---|---|---|
| Intent detection | Choice | "Udya Pune la jaycha aahe" → search 0.94 |
| Class preference | Choice | "AC madhe, pan swasta" → 3A 0.81 |
| Quota | Choice | "Tatkal madhe milel ka?" → Tatkal 0.97 |
| Confirmation | Noulli (yes/no) | "haan chalel, kar book" → yes 0.98 |
| Berth preference | Choice | "khalchi seat pahije, aai sobat aahe" → Lower 0.90 |
| Railway-related / off-topic check | Noulli | "ek joke sang" → off-topic 0.95 |
| User frustration | Score | "3 vela sangitla tari chuk!" → 0.88 → apology/human flow |
| Router: is the LLM needed? | Noulli | "PNR 4521367890" → no LLM, direct tool call |
| Train ranking | Score | How well each train matches the user's needs → sort |
| Cancel double-check | Noulli | "cancel kar... nako thamb" → cancel intent 0.32 → stop |

### LLM (Claude Sonnet) tasks

| Task | Why LLM? |
|---|---|
| Station and date extraction ("pudhchya shukravari", "Dadar te Nagpur") | Jev is weak on dates/numbers; extraction is not classification |
| Passenger details (name, age, gender) | Structured data from free text |
| Multi-step booking flow (what's asked, what's pending) | Reasoning over conversation state |
| Building tool-call arguments | Structured, context-dependent work |
| Waitlist / alternative suggestions ("3A full, 2A or another train?") | Trade-off reasoning |
| Writing replies to the user (Marathi, Hindi, English) | Natural language generation |
| Clarifying ambiguous queries | Deciding what to ask needs reasoning |

### Example booking flow (Mode B)

1. User: "Udya Pune te Mumbai, AC, 2 jan"
2. Jev: intent = search, class = 3A/AC; router → LLM needed for details
3. Claude: from = PUNE, to = CSMT, date = 22-10-2026, passengers = 2 → calls `search_trains`
4. Jev: match score for each train → trains sorted
5. Claude: writes the reply with the top 3 trains
6. User: "pahili chalel"
7. Jev: confirmation = yes 0.96, selection = option 1 (no LLM call)
8. Claude: asks for passenger details → calls `book_ticket` → confirmation reply with PNR

In Mode A, Claude does every step. In Mode B, 3–5 steps go to Jev, and some of them skip the LLM call entirely (step 7, direct PNR queries). The dashboard shows the actual cost and time saved.

## Fair comparison rules
- Same test set (~200 labelled queries + ~30 multi-turn booking scenarios), same prompts, same Claude model and effort, same machine/region.
- Every model call logged: mode, step, model, input/output tokens, latency ms, cost.
- Cost = tokens × price table (prices + date stored in config).
- Each scenario run 3–5 times, interleaved A/B; report p50/p95 latency, avg cost, intent accuracy, task success rate.
- Prompt caching setting identical in both modes.
- Projections (cost per 1M bookings) labelled as projections.

## Phases
0. Repo setup (backend/, frontend/, eval/, docs/)
1. Mock railway backend + tools (search_trains, check_availability, get_fare, book_ticket, cancel_ticket, pnr_status)
2. Mode A agent (Claude tool calling) + chat UI
3. Telemetry layer (per-call logging to SQLite)
4. Eval dataset + benchmark runner
5. Comparison dashboard (cost, latency, accuracy, per-step breakdown)
6. Mode B: DecisionModel interface + Jev adapter (+ optional open stand-in, clearly labelled)
7. Final benchmark runs + LinkedIn assets (README, architecture diagram, demo video, post)

## Progress
- [x] Phase 0: repo setup (backend/, frontend/, eval/, docs/, .env.example, .gitignore)
- [x] Phase 1: mock railway backend (36 stations, 23 trains, 6 tools, SQLite) + tests
- [x] Phase 2 (backend): Mode A Claude agent with tool loop, `/api/chat`
- [x] Phase 3: telemetry (model_calls, tool_calls, turns tables; cost from token counts; p50/p95 summary)
- [ ] Phase 2 (frontend): chat UI
- [x] Phase 4: eval datasets + benchmark runner
  - decisions bench: 215 labelled rows (intent 99, confirmation 34, class 32, quota 26, frustration 24), en/hi/mr incl. Devanagari
  - scenarios bench: 24 multi-turn conversations, fresh mock DB per run, judged on end state + tool args
  - `runs` table + `eval/results/<run_id>/`; modes interleaved per item; `--fake` for offline checks
  - Mode A classifier = Claude with the same model/effort; Jev adapter is a stub until API access
  - TODO before publishing: user reviews dataset labels
- [ ] Phase 5: dashboard
- [ ] Phase 6: Mode B (waiting for Jev API access)
- [ ] Phase 7: LinkedIn assets
