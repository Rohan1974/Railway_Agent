from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DATASETS = EVAL_DIR / "datasets"
RESULTS = EVAL_DIR / "results"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def file_sha(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def git_commit() -> str | None:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             cwd=EVAL_DIR, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                               cwd=EVAL_DIR, timeout=5).stdout.strip()
        return (sha + ("-dirty" if dirty else "")) or None
    except Exception:
        return None


def new_run_id(bench: str, fake: bool) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{'fake-' if fake else ''}{bench}-{ts}-{uuid.uuid4().hex[:4]}"


def mode_order(modes: list[str], i: int) -> list[str]:
    """Alternate the order of modes item by item so drift (network, rate limits) hits both equally."""
    return modes if i % 2 == 0 else list(reversed(modes))


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def latency_stats(values: list[float]) -> dict:
    return {"p50": percentile(values, .5), "p95": percentile(values, .95),
            "mean": (sum(values) / len(values)) if values else None, "n": len(values)}
