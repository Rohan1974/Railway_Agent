"""Central settings. Both modes read the same values so the comparison stays fair."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # project root (Railway_Agent/)
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1M tokens."""
    input: float
    output: float
    cache_write_5m: float = 0.0
    cache_write_1h: float = 0.0
    cache_read: float = 0.0
    source: str = ""
    checked_on: str = ""


# Keep this table in sync with the official pricing pages before every benchmark run.
PRICES: dict[str, ModelPrice] = {
    "claude-sonnet-5-5": ModelPrice(
        input=2.00, output=10.00, cache_write_5m=2.50, cache_write_1h=4.00, cache_read=0.10,
        source="https://platform.claude.com/docs/en/models/sonnet-5-5/overview",
        checked_on="2026-10-21",
    ),
    "claude-sonnet-5": ModelPrice(
        input=2.00, output=10.00, cache_write_5m=2.50, cache_write_1h=4.00, cache_read=0.20,
        source="https://platform.claude.com/docs/en/models/sonnet-5/overview",
        checked_on="2026-10-21",
    ),
    # Jev: output is free. Taken from launch coverage; re-check on TypeSafe's own pricing page once you have access.
    "jev": ModelPrice(
        input=0.042, output=0.0,
        source="TypeSafe AI launch coverage (Sept 2026) - verify on official page",
        checked_on="2026-10-21",
    ),
}


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    jev_api_key: str = field(default_factory=lambda: os.getenv("JEV_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"))
    # Sonnet 5 / 5.5 do not accept temperature; effort is the knob we hold constant across modes.
    claude_effort: str = field(default_factory=lambda: os.getenv("CLAUDE_EFFORT", "low"))
    claude_max_tokens: int = field(default_factory=lambda: int(os.getenv("CLAUDE_MAX_TOKENS", "4096")))
    db_path: Path = field(default_factory=lambda: ROOT / os.getenv("DB_PATH", "data/railway.db"))
    agent_max_iterations: int = 8


settings = Settings()
