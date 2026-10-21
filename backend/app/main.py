"""FastAPI app. Run from backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import PRICES, settings
from .db import connect, init_schema
from .railway.seed import seed
from .railway.service import RailwayService
from .railway.tools import execute_tool
from .telemetry import Telemetry

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = connect()
    init_schema(conn)
    if conn.execute("SELECT COUNT(*) FROM trains").fetchone()[0] == 0:
        seed(conn)
    state["conn"] = conn
    state["service"] = RailwayService(conn)
    state["telemetry"] = Telemetry(conn)
    yield
    conn.close()


app = FastAPI(title="Railway Agent - LLM vs Jev+LLM", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def get_agent(mode: str):
    key = f"agent_{mode}"
    if key not in state:
        if mode == "A":
            if not settings.anthropic_api_key:
                raise HTTPException(500, "ANTHROPIC_API_KEY is not set in .env")
            import anthropic
            from .agents.claude_agent import ClaudeAgent
            state[key] = ClaudeAgent(anthropic.Anthropic(api_key=settings.anthropic_api_key),
                                     state["service"], state["telemetry"], settings)
        elif mode == "B":
            raise HTTPException(501, "Mode B (Jev + LLM) is not built yet.")
        else:
            raise HTTPException(400, "mode must be 'A' or 'B'")
    return state[key]


class ChatIn(BaseModel):
    message: str
    mode: str = "A"
    conversation_id: str | None = None
    run_id: str | None = None


class ToolIn(BaseModel):
    args: dict = {}


@app.get("/health")
def health():
    return {"ok": True, "model": settings.claude_model, "effort": settings.claude_effort,
            "jev_configured": bool(settings.jev_api_key)}


@app.get("/api/stations")
def stations():
    return [dict(r) for r in state["conn"].execute("SELECT * FROM stations ORDER BY city, name")]


@app.post("/api/tools/{name}")
def run_tool(name: str, body: ToolIn):
    """Call a railway tool directly (no model). Useful for testing the mock backend."""
    result, ok = execute_tool(state["service"], name, body.args)
    if not ok:
        raise HTTPException(400, result["error"])
    return result


@app.post("/api/chat")
def chat(body: ChatIn):
    return get_agent(body.mode).chat(body.message, body.conversation_id, body.run_id)


@app.get("/api/metrics/summary")
def metrics_summary(run_id: str | None = None):
    return {"summary": state["telemetry"].summary(run_id),
            "prices": {k: vars(v) for k, v in PRICES.items()}}


@app.get("/api/metrics/calls")
def metrics_calls(limit: int = 200):
    rows = state["conn"].execute("SELECT * FROM model_calls ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
