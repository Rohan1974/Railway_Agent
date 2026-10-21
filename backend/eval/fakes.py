"""Offline stand-ins for the Anthropic client, used by `--fake` and tests. Results are marked fake."""
from __future__ import annotations

import json
from types import SimpleNamespace as NS

from app.decisions.tasks import TASKS


def _usage(i: int, o: int):
    return NS(input_tokens=i, output_tokens=o, cache_read_input_tokens=0, cache_creation_input_tokens=0,
              output_tokens_details=None)


class FakeDeciderMessages:
    """Always answers the first option, so accuracy numbers from a fake run mean nothing."""
    def create(self, system, messages, **kw):
        task = next(t for t in TASKS.values() if t.question in system)
        label = next(iter(task.options))
        return NS(stop_reason="end_turn", usage=_usage(250, 12),
                  content=[NS(type="text", text=json.dumps({"label": label}))])


class FakeAgentMessages:
    """Replies with text and never calls tools."""
    def create(self, **kw):
        return NS(stop_reason="end_turn", usage=_usage(1500, 60), content=[NS(type="text", text="(fake reply)")])


def fake_client(kind: str):
    return NS(messages=FakeDeciderMessages() if kind == "decisions" else FakeAgentMessages())
