# Eval datasets

## decisions.jsonl

One row = one classification decision: `{id, task, text, lang, label, context?}`.

| Task | Labels | Rows |
|---|---|---|
| intent | search_trains, check_availability, get_fare, book_ticket, pnr_status, cancel_ticket, provide_details, greeting, off_topic | 99 |
| travel_class | SL, 3A, 2A, 1A, CC, EC, none | 32 |
| quota | GN, TQ, LD, SS | 26 |
| confirmation | yes, no, unclear (uses `context`, the assistant's question) | 34 |
| frustration | frustrated, not_frustrated | 24 |

Languages: `en`, `hi` (Hindi in Latin script), `hi-dev` (Devanagari), `mr` (Marathi in Latin script), `mr-dev` (Devanagari).

Label definitions live in `backend/app/decisions/tasks.py`. Both models see the same definitions.

Labelling rules worth knowing:
- `travel_class = none` when no class is named, including a generic "AC".
- `quota = GN` when no quota is mentioned.
- `confirmation = no` also covers "yes, but change X" (the proposal is not accepted as is).
- Flights, buses, cabs and hotels are `off_topic`, even when a station is mentioned.

## scenarios.json

Scripted multi-turn conversations. The runner pins `TODAY` to the file's `today` so relative dates
("udya", "kal", "parso") resolve the same way on every run. Each scenario runs in a fresh copy of the
mock railway DB and is judged by `expect` checks on the final state (bookings made, cancellations,
tools called and their arguments).

## Review before publishing

These rows were drafted with Claude's help. Before you publish numbers, read through the labels
(especially confirmation and frustration, which are the most subjective) and fix anything you disagree
with. If you change a file, its hash changes and new runs record the new `dataset_sha`.
