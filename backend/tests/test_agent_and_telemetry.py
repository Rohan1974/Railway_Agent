from types import SimpleNamespace as NS

import pytest

from app.agents.claude_agent import ClaudeAgent
from app.config import PRICES, Settings, settings
from app.telemetry import Usage, cost_usd


class FakeMessages:
    """Scripted Claude: first asks for search_trains, then answers."""
    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        if len(self.calls) == 1:
            return NS(stop_reason="tool_use",
                      usage=NS(input_tokens=1200, output_tokens=150, cache_read_input_tokens=0,
                               cache_creation_input_tokens=900, output_tokens_details=NS(thinking_tokens=60)),
                      content=[NS(type="tool_use", id="tu_1", name="search_trains",
                                  input={"from_station": "Mumbai", "to_station": "Pune", "journey_date": "2026-10-22"})])
        return NS(stop_reason="end_turn",
                  usage=NS(input_tokens=300, output_tokens=120, cache_read_input_tokens=900,
                           cache_creation_input_tokens=0, output_tokens_details=None),
                  content=[NS(type="text", text="Udya Mumbai-Pune sathi 5 trains aahet.")])


# Tests use whatever model .env / config.py selects, so switching models never breaks them.
MODEL = settings.claude_model


def test_configured_model_has_a_price():
    assert MODEL in PRICES, f"CLAUDE_MODEL={MODEL} has no entry in PRICES (config.py)"


def test_cost_formula():
    p = PRICES[MODEL]
    u = Usage(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000, cache_write_tokens=1_000_000)
    assert cost_usd(MODEL, u) == pytest.approx(p.input + p.output + p.cache_read + p.cache_write_5m)
    assert cost_usd("jev", Usage(input_tokens=1_000_000, output_tokens=999)) == pytest.approx(0.042)


def test_mode_a_agent_loop_logs_everything(svc, telemetry, conn):
    fake = FakeMessages()
    # explicit settings so the test does not depend on CLAUDE_EFFORT in .env
    agent = ClaudeAgent(NS(messages=fake), svc, telemetry,
                        Settings(anthropic_api_key="x", claude_model=MODEL, claude_effort="low"))
    out = agent.chat("udya mumbai te pune train", run_id="r1")

    assert out["reply"].startswith("Udya")
    assert out["metrics"]["llm_calls"] == 2 and out["metrics"]["tool_calls"] == 1
    # same settings are sent on every call
    assert all(c["model"] == MODEL and c["output_config"] == {"effort": "low"} for c in fake.calls)
    assert "temperature" not in fake.calls[0]
    # tool result was passed back to Claude
    tool_msg = fake.calls[1]["messages"][2]["content"][0]
    assert tool_msg["type"] == "tool_result" and not tool_msg["is_error"]

    rows = conn.execute("SELECT * FROM model_calls ORDER BY id").fetchall()
    assert len(rows) == 2 and rows[0]["thinking_tokens"] == 60
    p = PRICES[MODEL]
    expected = ((1200 + 300) * p.input + (150 + 120) * p.output + 900 * p.cache_write_5m + 900 * p.cache_read) / 1e6
    assert out["metrics"]["cost_usd"] == pytest.approx(expected, abs=1e-6)
    s = telemetry.summary("r1")["A_llm_only"]
    assert s["turns"] == 1 and s["llm_calls_per_turn"] == 2


def test_failed_call_is_logged(svc, telemetry, conn):
    class Boom:
        def create(self, **kw):
            raise RuntimeError("network down")
    agent = ClaudeAgent(NS(messages=Boom()), svc, telemetry, Settings(anthropic_api_key="x"))
    with pytest.raises(RuntimeError):
        agent.chat("hi")
    row = conn.execute("SELECT * FROM model_calls").fetchone()
    assert row["ok"] == 0 and "network down" in row["error"]
