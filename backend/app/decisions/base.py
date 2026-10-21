from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..telemetry import TurnContext


@dataclass
class Decision:
    task: str
    label: str | None                     # None when the model output could not be parsed
    probabilities: dict[str, float] = field(default_factory=dict)  # Jev returns these; Claude does not
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    raw: str = ""

    @property
    def confidence(self) -> float | None:
        if self.label is None or not self.probabilities:
            return None
        return self.probabilities.get(self.label)


class DecisionModel(Protocol):
    name: str   # used as the mode-specific provider label

    def decide(self, ctx: TurnContext, task: str, text: str, context: str | None = None) -> Decision:
        """Answer one classification task. Must log its own model call to telemetry."""
        ...
