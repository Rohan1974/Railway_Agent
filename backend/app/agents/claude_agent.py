"""Mode A: Claude does everything (classification, extraction, reasoning, tool calls, replies)."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from ..config import Settings
from ..railway.service import RailwayService, today
from ..railway.tools import TOOL_SCHEMAS, execute_tool
from ..telemetry import Telemetry, TurnContext, Usage
from .prompts import BASE_SYSTEM_PROMPT


class ClaudeAgent:
    mode = "A_llm_only"

    def __init__(self, client: Any, service: RailwayService, telemetry: Telemetry, settings: Settings,
                 prompt_caching: bool = True):
        self.client = client
        self.service = service
        self.telemetry = telemetry
        self.settings = settings
        self.prompt_caching = prompt_caching
        self.conversations: dict[str, list[dict]] = {}

    # Hooks Mode B overrides.
    def system_prompt(self, ctx: TurnContext, user_text: str) -> list[dict]:
        block = {"type": "text", "text": BASE_SYSTEM_PROMPT.format(today=today().isoformat())}
        if self.prompt_caching:
            block["cache_control"] = {"type": "ephemeral"}
        return [block]

    def _call_claude(self, ctx: TurnContext, step: str, system: list[dict], messages: list[dict]):
        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(
                model=self.settings.claude_model, max_tokens=self.settings.claude_max_tokens,
                system=system, tools=TOOL_SCHEMAS, messages=messages,
                output_config={"effort": self.settings.claude_effort},
            )
        except Exception as e:  # log the failed call, then re-raise
            self.telemetry.model_call(ctx, step=step, provider="anthropic", model=self.settings.claude_model,
                                      usage=Usage(), latency_ms=(time.perf_counter() - t0) * 1000,
                                      ok=False, error=f"{type(e).__name__}: {e}")
            raise
        self.telemetry.model_call(ctx, step=step, provider="anthropic", model=self.settings.claude_model,
                                  usage=Usage.from_anthropic(resp.usage),
                                  latency_ms=(time.perf_counter() - t0) * 1000)
        return resp

    def _run_tools(self, ctx: TurnContext, content: list[Any]) -> list[dict]:
        results = []
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue
            t0 = time.perf_counter()
            result, ok = execute_tool(self.service, block.name, dict(block.input))
            self.telemetry.tool_call(ctx, block.name, (time.perf_counter() - t0) * 1000, ok)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False), "is_error": not ok})
        return results

    def chat(self, user_text: str, conversation_id: str | None = None, run_id: str | None = None) -> dict:
        conversation_id = conversation_id or uuid.uuid4().hex
        messages = self.conversations.setdefault(conversation_id, [])
        ctx = TurnContext(mode=self.mode, conversation_id=conversation_id, run_id=run_id)
        messages.append({"role": "user", "content": user_text})
        system = self.system_prompt(ctx, user_text)

        reply = ""
        for i in range(self.settings.agent_max_iterations):
            resp = self._call_claude(ctx, f"agent_call_{i}", system, messages)
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "tool_use":
                messages.append({"role": "user", "content": self._run_tools(ctx, resp.content)})
                continue
            reply = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
            break
        else:
            reply = "Sorry, I could not finish this request. Please try again."

        metrics = self.telemetry.finish_turn(ctx, user_text, reply)
        return {"conversation_id": conversation_id, "mode": self.mode, "reply": reply, "metrics": metrics}
