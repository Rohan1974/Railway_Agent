"""Mode A classifier: Claude answers the decision tasks (same model and effort as the agent)."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from ..config import Settings
from ..telemetry import Telemetry, TurnContext, Usage
from .base import Decision
from .tasks import TASKS

_JSON = re.compile(r"\{.*?\}", re.S)


def build_prompt(task_name: str) -> str:
    t = TASKS[task_name]
    opts = "\n".join(f"- {k}: {v}" for k, v in t.options.items())
    return (
        "You are a classifier inside an Indian Railways ticket booking assistant. "
        "Messages may be in English, Hindi, Marathi or a mix, in Latin or Devanagari script.\n\n"
        f"Question: {t.question}\n\nOptions:\n{opts}\n\n"
        'Reply with only a JSON object and nothing else: {"label": "<one option>"}'
    )


def parse_label(text: str, task_name: str) -> str | None:
    options = TASKS[task_name].options
    for m in _JSON.finditer(text or ""):
        try:
            label = json.loads(m.group(0)).get("label")
        except (json.JSONDecodeError, AttributeError):
            continue
        if label in options:
            return label
    return None


class ClaudeDecider:
    name = "claude"

    def __init__(self, client: Any, telemetry: Telemetry, settings: Settings):
        self.client = client
        self.telemetry = telemetry
        self.settings = settings

    def decide(self, ctx: TurnContext, task: str, text: str, context: str | None = None) -> Decision:
        user = f"User message: {text}"
        if TASKS[task].uses_context and context:
            user = f"Assistant's previous message: {context}\n\n{user}"
        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(
                model=self.settings.claude_model, max_tokens=self.settings.claude_max_tokens,
                system=build_prompt(task), messages=[{"role": "user", "content": user}],
                output_config={"effort": self.settings.claude_effort},
            )
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            self.telemetry.model_call(ctx, step=f"decision:{task}", provider="anthropic",
                                      model=self.settings.claude_model, usage=Usage(), latency_ms=latency,
                                      ok=False, error=f"{type(e).__name__}: {e}")
            raise
        latency = (time.perf_counter() - t0) * 1000
        raw = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        cost = self.telemetry.model_call(ctx, step=f"decision:{task}", provider="anthropic",
                                         model=self.settings.claude_model, usage=Usage.from_anthropic(resp.usage),
                                         latency_ms=latency)
        return Decision(task=task, label=parse_label(raw, task), latency_ms=latency, cost_usd=cost, raw=raw)
