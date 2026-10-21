"""Mode B classifier: Jev (TypeSafe AI).

Not implemented yet: we don't have API access, and the request/response format must come from
TypeSafe's official docs, not from guesses. When access arrives, implement `decide` so it:
  1. sends `text` (+ `context` for tasks with uses_context) as state, and the task as a
     `jev_type` question (choice / noulli) with TASKS[task].options,
  2. returns Decision(label=argmax, probabilities=..., latency_ms, cost_usd),
  3. logs the call with telemetry.model_call(..., provider="typesafe", model="jev", kind="decision")
     using the input token count Jev reports (cost uses PRICES["jev"]).
"""
from __future__ import annotations

from ..config import Settings
from ..telemetry import Telemetry, TurnContext
from .base import Decision


class JevNotConfigured(RuntimeError):
    pass


class JevDecider:
    name = "jev"

    def __init__(self, telemetry: Telemetry, settings: Settings):
        if not settings.jev_api_key:
            raise JevNotConfigured("JEV_API_KEY is not set. Mode B needs Jev API access.")
        self.telemetry = telemetry
        self.settings = settings

    def decide(self, ctx: TurnContext, task: str, text: str, context: str | None = None) -> Decision:
        raise NotImplementedError("Jev adapter pending: implement from TypeSafe's API docs once you have access.")
